# indexer.py
import httpx
import asyncio
import json
import time
from database import init_db, get_db

# Contract Addresses
HEN_V2 = "KT1HbQepzV1nVGg8QVznG7z4RcHseD5kwqBn"
TEIA_MARKET = "KT1PHubm9HtyQEJ4BBpMTVomq6mhbfNZ9z5w"
TARGETS = [HEN_V2, TEIA_MARKET]

# Settings
BATCH_SIZE = 50       # How many collects to fetch per loop
RATE_LIMIT_DELAY = 1.0 # Seconds to sleep between loops (Be nice to TzKT)

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
    print(f"📡 Starting Forward Sync Daemon...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # 1. Initialize Cursor
        cursor_id = await get_starting_cursor(client)
        
        while True:
            try:
                # --- STEP 1: Fetch Next Batch of Intents ---
                # We use id.gt (Greater Than) to move forward in time
                r_collects = await client.get(
                    "https://api.tzkt.io/v1/operations/transactions",
                    params={
                        "target.in": ",".join(TARGETS),
                        "entrypoint": "collect",
                        "status": "applied",
                        "limit": BATCH_SIZE,
                        "sort.asc": "id",       # Critical: Oldest to Newest
                        "id.gt": cursor_id,     # Get items NEWER than cursor
                        "select": "hash,sender,timestamp,id" 
                    }
                )
                
                if r_collects.status_code != 200:
                    print(f"⚠️ API Error {r_collects.status_code}. Retrying in 5s...")
                    await asyncio.sleep(5)
                    continue
                
                collects = r_collects.json()
                
                if not collects:
                    print("💤 caught up to tip. Sleeping 10s...")
                    await asyncio.sleep(10)
                    continue

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
                    # Batch fetch transfers
                    t_response = await client.get(
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
                                
                                # Resolve Artist
                                creators = metadata.get("creators")
                                if isinstance(creators, list) and len(creators) > 0:
                                    artist = creators[0]
                                else:
                                    artist = metadata.get("issuer")
                                
                                if artist: artist = artist.strip()

                                if buyer and artist and buyer != artist:
                                    db["edges"].insert({
                                        "source": buyer,
                                        "target": artist,
                                        "token_id": str(token.get("tokenId")),
                                        "contract": token.get("contract", {}).get("address"),
                                        "timestamp": tx.get("timestamp")
                                    }, pk=("source", "target", "token_id"), replace=True)
                                    trace_count += 1
                            except:
                                continue

                # --- STEP 4: Update Cursor & Rate Limit ---
                # The new cursor is the ID of the LAST item in the 'collects' batch
                last_item_id = collects[-1]["id"]
                await save_cursor(last_item_id)
                cursor_id = last_item_id
                
                print(f"✅ Synced {len(collects)} ops up to ID {cursor_id}. Found {trace_count} connections.")
                
                # Be polite
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