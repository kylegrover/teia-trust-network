# indexer.py
import httpx
import asyncio
import json
from datetime import datetime
from database import init_db, get_db

# Contract Addresses
HEN_V2 = "KT1HbQepzV1nVGg8QVznG7z4RcHseD5kwqBn"
TEIA_MARKET = "KT1PHubm9HtyQEJ4BBpMTVomq6mhbfNZ9z5w"
TARGETS = [HEN_V2, TEIA_MARKET]

# Settings
BATCH_SIZE = 100       # How many collects to fetch per loop
RATE_LIMIT_DELAY = 1.0 # Seconds to sleep between loops (Be nice to TzKT)

# --- helpers: retries + canonical creator resolution ---
_canonical_creator_cache = {}

def _normalize_addr_like(v):
    """Return a normalized address string from common TzKT shapes (str, dict with address/value)."""
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        return (v.get('address') or v.get('value') or v.get('tz') or v.get('string')) and str(
            v.get('address') or v.get('value') or v.get('tz') or v.get('string')
        ).strip()
    return str(v).strip()

async def get_with_retries(client, url, params=None, retries=3, backoff=1.0):
    """Simple retry for transient 5xx / 429 responses."""
    for attempt in range(1, retries + 1):
        r = await client.get(url, params=params)
        if r.status_code == 200:
            return r
        if r.status_code in (429, 502, 503, 504) and attempt < retries:
            await asyncio.sleep(backoff * (2 ** (attempt - 1)))
            continue
        return r

async def fetch_canonical_creator(client, contract_addr, token_id):
    """Prefer authoritative on-chain minter/firstMinter from TzKT; fall back to token metadata.
    Results are cached in-memory for the run.
    """
    key = (contract_addr, str(token_id))
    if key in _canonical_creator_cache:
        return _canonical_creator_cache[key]

    try:
        r = await get_with_retries(client, "https://api.tzkt.io/v1/tokens", params={
            "contract": contract_addr,
            "tokenId": token_id,
            "select": "metadata,firstMinter"
        })
        if r.status_code == 200:
            items = r.json()
            if items:
                token = items[0]

                # firstMinter may be a string or an object; normalize safely
                fm_raw = token.get("firstMinter") or token.get("first_minter")
                fm = _normalize_addr_like(fm_raw)
                if fm:
                    _canonical_creator_cache[key] = fm
                    return fm

                # metadata.creators entries are sometimes objects
                md = token.get("metadata") or {}
                creators = md.get("creators")
                if isinstance(creators, list) and creators:
                    candidate = creators[0]
                    cand_addr = _normalize_addr_like(candidate)
                    if cand_addr:
                        _canonical_creator_cache[key] = cand_addr
                        return cand_addr

                issuer = md.get("issuer")
                issuer_addr = _normalize_addr_like(issuer)
                if issuer_addr:
                    _canonical_creator_cache[key] = issuer_addr
                    return issuer_addr
    except Exception as e:
        print(f"⚠️ canonical-creator lookup failed for {contract_addr}/{token_id}: {e}")

    _canonical_creator_cache[key] = None
    return None

async def get_starting_cursor(client):
    """
    Determines where to start indexing.
    1. Checks DB for last processed ID.
    2. If empty, asks API for the very first operation ID of these contracts.
    """
    db = get_db()
    try:
        row = db["state"].get("last_processed_id")
        print(f"🔄 Resuming from ID: {row['value']}")
        return row['value']
    except:
        pass # Key doesn't exist yet

    print("🆕 No local history found. Finding genesis operation...")
    response = await client.get(
        "https://api.tzkt.io/v1/operations/transactions",
        params={
            "target.in": ",".join(TARGETS),
            "entrypoint": "collect",
            "status": "applied",
            "limit": 1,
            "sort.asc": "id", # Oldest first
            "select": "id"
        }
    )
    start_id = response.json()[0] - 1 # Start just before the first one
    print(f"🏁 Starting from Genesis ID: {start_id}")
    return start_id

async def save_cursor(last_id):
    """Save our progress to the DB."""
    db = get_db()
    db["state"].insert(
        {"key": "last_processed_id", "value": last_id}, 
        pk="key", 
        replace=True
    )

async def sync_forward():
    print(f"📡 Starting Forward Sync...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Initialize Cursor
        cursor_id = await get_starting_cursor(client)
        start_time = datetime.now()
        total_synced = 0
        
        while True:
            try:
                r_collects = await client.get(
                    "https://api.tzkt.io/v1/operations/transactions",
                    params={
                        "target.in": ",".join(TARGETS),
                        "entrypoint": "collect",
                        "status": "applied",
                        "limit": BATCH_SIZE,
                        "sort.asc": "id",
                        "id.gt": cursor_id,
                        "select": "hash,sender,timestamp,id" 
                    }
                )
                
                if r_collects.status_code != 200:
                    print(f"⚠️ API Error {r_collects.status_code}. Sleeping...")
                    await asyncio.sleep(5)
                    continue
                
                collects = r_collects.json()
                if not collects:
                    print("💤 caught up to tip. Sleeping 10s...")
                    await asyncio.sleep(10)
                    continue
                
                # --- Status Prep ---
                current_batch_time = collects[-1]["timestamp"]
                # Convert TzKT timestamp (e.g., 2021-03-01T...) to pretty format
                dt_obj = datetime.strptime(current_batch_time, "%Y-%m-%dT%H:%M:%SZ")
                pretty_date = dt_obj.strftime("%b %d, %Y")

                # --- STEP 2: Trace Execution (Get Internal Ops) ---
                group_hashes = list(set([c["hash"] for c in collects]))
                valid_op_ids = []
                
                # Fetch detailed traces for these groups
                # Processing in mini-batches to prevent URL overflow
                trace_chunk_size = 10
                for i in range(0, len(group_hashes), trace_chunk_size):
                    chunk = group_hashes[i:i + trace_chunk_size]
                    trace_tasks = [client.get(f"https://api.tzkt.io/v1/operations/{h}") for h in chunk]
                    responses = await asyncio.gather(*trace_tasks)
                    
                    for r in responses:
                        if r.status_code == 200:
                            ops = r.json()
                            valid_op_ids.extend([op["id"] for op in ops])
                
                # --- STEP 3: Fetch Resulting Transfers ---
                trace_count = 0
                if valid_op_ids:
                    # Batch fetch transfers (with retries)
                    t_response = await get_with_retries(client,
                        "https://api.tzkt.io/v1/tokens/transfers",
                        params={
                            "transactionId.in": ",".join(map(str, valid_op_ids)),
                            "select": "to,token,transactionId,timestamp"
                        }
                    )

                    if t_response.status_code == 200:
                        transfers = t_response.json()
                        db = get_db() # Get thread-safe connection

                        for tx in transfers:
                            try:
                                buyer = tx.get("to", {}).get("address")
                                token = tx.get("token", {})
                                metadata = token.get("metadata", {})

                                # Resolve Artist (prefer on-chain canonical minter)
                                artist = None
                                token_contract = token.get("contract", {}).get("address")
                                token_id = token.get("tokenId") or token.get("token_id")
                                if token_contract and token_id is not None:
                                    artist = await fetch_canonical_creator(client, token_contract, token_id)

                                # fallback to embedded metadata (handle dict/list shapes safely)
                                if not artist:
                                    creators = metadata.get("creators")
                                    if isinstance(creators, list) and len(creators) > 0:
                                        artist = _normalize_addr_like(creators[0])
                                    else:
                                        artist = _normalize_addr_like(metadata.get("issuer"))

                                # ensure artist is a trimmed string or None
                                if artist:
                                    artist = str(artist).strip()

                                if buyer and artist and buyer != artist:
                                    db["edges"].insert({
                                        "source": buyer,
                                        "target": artist,
                                        "token_id": str(token.get("tokenId")),
                                        "contract": token.get("contract", {}).get("address"),
                                        "timestamp": tx.get("timestamp")
                                    }, pk=("source", "target", "token_id"), replace=True)
                                    trace_count += 1
                            except Exception as e:
                                print(f"⚠️ parse error (transfer) tx={tx.get('transactionId')} err={e}")
                                continue

                # --- STEP 4: Human-Readable Output ---
                last_item_id = collects[-1]["id"]
                await save_cursor(last_item_id)
                cursor_id = last_item_id
                total_synced += len(collects)
                
                # Progress Bar / Status Line
                print(f"📅 [{pretty_date}] | 📈 Total Ops: {total_synced} | ✨ New Edges: +{trace_count} | ID: {cursor_id}")
    
                await asyncio.sleep(RATE_LIMIT_DELAY)

            except Exception as e:
                print(f"❌ Crash in loop: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    init_db()
    try:
        asyncio.run(sync_forward())
    except KeyboardInterrupt:
        print("\n🛑 Sync stopped by user.")