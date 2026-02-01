import asyncio
import httpx
import sqlite3
import json
import logging
from typing import List, Dict

# --- CONFIGURATION ---
DB_FILE = "teia_index.db"
# Contracts
HEN_MINTER = "KT1Hkg5qeNhfwpKW4fXvq7HGZB9z2EnmCCA9"
MARKETS = {
    "V1": "KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton",
    "V2": "KT1HbQepzV1nVGg8QVznG7z4RcHseD5kwqBn",
    "TEIA": "KT1PHubm9HtyQEJ4BBpMTVomq6mhbfNZ9z5w"
}
MARKET_ADDRESSES = list(MARKETS.values())

# Settings
BATCH_SIZE = 1000  # For BigMap fetching
OPS_BATCH_SIZE = 500  # For Transaction fetching
CONCURRENCY = 1  # Max parallel requests

RATE_LIMIT_DELAY = 2.0 # Seconds to sleep between loops (Be nice to TzKT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. TOKENS (The Objects)
    c.execute("""CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY,
        minter TEXT,
        title TEXT,
        artifact_uri TEXT,
        metadata_uri TEXT,
        royalties INTEGER,
        supply INTEGER
    )""")

    # 2. HOLDERS (The Ledger)
    c.execute("""CREATE TABLE IF NOT EXISTS holders (
        token_id INTEGER,
        address TEXT,
        amount INTEGER,
        PRIMARY KEY (token_id, address)
    )""")

    # 3. EVENTS (Market History)
    c.execute("""CREATE TABLE IF NOT EXISTS events (
        op_hash TEXT,
        op_id INTEGER,
        timestamp DATETIME,
        type TEXT,  -- 'LIST', 'SALE', 'CANCEL'
        contract TEXT, -- 'V1', 'V2', 'TEIA'
        token_id INTEGER,
        seller TEXT,
        buyer TEXT,
        amount INTEGER,
        price_mutez INTEGER,
        PRIMARY KEY (op_id)
    )""")

    # 4. STATE (Cursor)
    c.execute("""CREATE TABLE IF NOT EXISTS state (
        key TEXT PRIMARY KEY, 
        value INTEGER
    )""")
    
    conn.commit()
    return conn

# --- HELPERS ---
def hex_to_utf8(hex_str: str) -> str:
    """Decodes Tezos hex strings (often used in metadata)."""
    try:
        return bytes.fromhex(hex_str).decode('utf-8')
    except:
        return hex_str

def get_bigmap_ptr(client, contract, name):
    """Finds the active BigMap ID for a specific storage key."""
    # We use a synchronous call logic here wrapped in async for simplicity in flow
    return None # Placeholder, we do this dynamically below

# --- PHASE 1: SNAPSHOT (BigMaps) - ROBUST & RESUMABLE ---
async def sync_tokens_and_holders(client: httpx.AsyncClient, conn: sqlite3.Connection):
    """
    Downloads current state of Tokens/Holders.
    Features:
    1. Robust BigMap discovery (fixes StopIteration).
    2. Checks DB for progress to resume if interrupted.
    """
    logger.info("🔍 Fetching BigMap Pointers...")
    
    # 1. Get BigMap IDs with Fallbacks
    r = await client.get(f"https://api.tzkt.io/v1/contracts/{HEN_MINTER}/bigmaps")
    bigmaps = r.json()
    
    # Helper to find ptr safely
    def find_ptr(name_variants, default_id=None):
        for b in bigmaps:
            path = b.get('path', '')
            if path in name_variants:
                return b['ptr']
        return default_id

    # HEN Contract Specifics:
    # token_metadata is usually ptr 514
    # ledger is usually ptr 511
    metadata_ptr = find_ptr(['token_metadata', 'assets.token_metadata'], default_id=514)
    ledger_ptr = find_ptr(['ledger', 'assets.ledger'], default_id=511)
    
    if not metadata_ptr or not ledger_ptr:
        logger.error(f"❌ Could not find BigMaps! Found: {[b.get('path') for b in bigmaps]}")
        return

    logger.info(f"   -> Metadata Ptr: {metadata_ptr}")
    logger.info(f"   -> Ledger Ptr: {ledger_ptr}")

    # --- PART A: SYNC TOKENS ---
    # Check saved progress
    c = conn.cursor()
    c.execute("SELECT value FROM state WHERE key='token_offset'")
    row = c.fetchone()
    token_offset = row[0] if row else 0
    
    if token_offset > 0:
        logger.info(f"🔄 Resuming Token Sync from offset {token_offset}")
    else:
        logger.info("📦 Starting Token Sync...")

    while True:
        r = await client.get(f"https://api.tzkt.io/v1/bigmaps/{metadata_ptr}/keys", params={
            "limit": BATCH_SIZE,
            "offset": token_offset,
            "select": "key,value" 
        })
        data = r.json()
        if not data: break
        
        rows = []
        for item in data:
            try:
                tid = item['key']
                # Extract hex string from map (usually key "")
                # Handle cases where value might be just the bytes or a dict
                val = item['value']
                raw_bytes = ""
                
                if isinstance(val, dict):
                    raw_bytes = val.get('token_info', {}).get('', '')
                elif isinstance(val, str):
                    # Sometimes raw value is returned if not decodable
                    raw_bytes = val
                
                meta_uri = hex_to_utf8(raw_bytes)
                rows.append((tid, "Unknown", "Unknown", "Unknown", meta_uri, 0, 0))
            except Exception:
                continue
        
        if rows:
            conn.executemany("INSERT OR REPLACE INTO tokens (id, minter, title, artifact_uri, metadata_uri, royalties, supply) VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
            
            # SAVE PROGRESS
            token_offset += len(data)
            conn.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('token_offset', ?)", (token_offset,))
            conn.commit()
            
        print(f"   -> Synced {token_offset} tokens...", end="\r")
        
        # Stop if we fetched fewer than batch size (end of list)
        if len(data) < BATCH_SIZE: break

        # rate limit
        await asyncio.sleep(RATE_LIMIT_DELAY)
            
    print(f"\n✅ Tokens Synced.")

    # --- PART B: SYNC HOLDERS ---
    # Check saved progress
    c.execute("SELECT value FROM state WHERE key='holder_offset'")
    row = c.fetchone()
    holder_offset = row[0] if row else 0

    if holder_offset > 0:
        logger.info(f"🔄 Resuming Holder Sync from offset {holder_offset}")
    else:
        logger.info("👥 Starting Holder Sync...")

    while True:
        r = await client.get(f"https://api.tzkt.io/v1/bigmaps/{ledger_ptr}/keys", params={
            "limit": BATCH_SIZE,
            "offset": holder_offset,
            "active": "true",
            "select": "key,value" 
        })
        data = r.json()
        if not data: break
        
        rows = []
        for item in data:
            try:
                tid = item['key']['nat']
                owner = item['key']['address']
                amount = int(item['value'])
                if amount > 0:
                    rows.append((tid, owner, amount))
            except: continue
            
        if rows:
            conn.executemany("INSERT OR REPLACE INTO holders (token_id, address, amount) VALUES (?, ?, ?)", rows)
            
            # SAVE PROGRESS
            holder_offset += len(data)
            conn.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('holder_offset', ?)", (holder_offset,))
            conn.commit()
            
        print(f"   -> Synced {holder_offset} holdings...", end="\r")
        
        if len(data) < BATCH_SIZE: break

        # rate limit
        await asyncio.sleep(RATE_LIMIT_DELAY)
            
    print(f"\n✅ Holdings Synced.")

# --- PHASE 2: HISTORY (Transactions) ---
async def sync_market_history(client: httpx.AsyncClient, conn: sqlite3.Connection):
    """
    Downloads historical 'collect' and 'swap' operations.
    """
    logger.info("📜 Syncing Market History...")
    
    # Get last synced ID
    c = conn.cursor()
    c.execute("SELECT value FROM state WHERE key='last_op_id'")
    row = c.fetchone()
    last_id = row[0] if row else 0
    
    while True:
        r = await client.get("https://api.tzkt.io/v1/operations/transactions", params={
            "target.in": ",".join(MARKET_ADDRESSES),
            "entrypoint.in": "collect,swap,cancel_swap",
            "status": "applied",
            "limit": OPS_BATCH_SIZE,
            "sort.asc": "id",
            "id.gt": last_id
        })
        ops = r.json()
        
        if not ops:
            logger.info("💤 History fully synced.")
            break
            
        events = []
        for op in ops:
            try:
                entry = op['parameter']['entrypoint']
                val = op['parameter']['value']
                contract_addr = op['target']['address']
                
                # Identify Market Version
                version = "UNKNOWN"
                for k, v in MARKETS.items():
                    if v == contract_addr: version = k

                # PARSE EVENT
                if entry == "collect":
                    # V1/V2/Teia collect params are usually { objkt_id: ..., ... }
                    # Note: Parameter structures vary slightly by contract version.
                    # This logic assumes standard Teia/HEN structure.
                    objkt_id = val.get('objkt_id', val.get('objkt_amount')) # Field names vary
                    if not objkt_id and isinstance(val, int): objkt_id = val # Sometimes it's just an int
                    
                    # If we can't find ID in param, try diff structure (older V1)
                    if not objkt_id and 'swap_id' in val:
                         # Requires a join with swap table to get Token ID. 
                         # For MVP, we skip complex V1 swap lookups.
                         continue 

                    events.append((
                        op['hash'], op['id'], op['timestamp'], 
                        "SALE", version, objkt_id, 
                        op['diffs'][0]['content']['address'] if 'diffs' in op else "Unknown", # Seller (approx)
                        op['sender']['address'], # Buyer
                        1, op['amount'] # Price is usually the tx amount
                    ))

                elif entry == "swap":
                    # Listing
                    objkt_id = val.get('objkt_id')
                    price = val.get('xtz_per_objkt')
                    amount = val.get('objkt_amount')
                    
                    events.append((
                        op['hash'], op['id'], op['timestamp'], 
                        "LIST", version, objkt_id, 
                        op['sender']['address'], # Seller
                        None, # No Buyer yet
                        amount, price
                    ))

            except Exception as e:
                # logger.warning(f"Parse error on {op['id']}: {e}")
                pass

        if events:
            # Using 'INSERT OR IGNORE' to prevent duplicates if restarting
            conn.executemany("""
                INSERT OR IGNORE INTO events 
                (op_hash, op_id, timestamp, type, contract, token_id, seller, buyer, amount, price_mutez) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, events)
            
            # Update Cursor
            last_id = ops[-1]['id']
            conn.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('last_op_id', ?)", (last_id,))
            conn.commit()
            
        print(f"   -> Processed up to ID {last_id}...", end="\r")
        await asyncio.sleep(RATE_LIMIT_DELAY) # Be nice to API

# --- MAIN LOOP ---
async def main():
    conn = init_db()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Base State (Run this once, or periodically)
        print("--- PHASE 1: STATE SNAPSHOT ---")
        await sync_tokens_and_holders(client, conn)
        
        # Step 2: History (Runs until caught up)
        print("\n--- PHASE 2: HISTORY BACKFILL ---")
        await sync_market_history(client, conn)
        
        print("\n✅ Indexer is up to date!")
        conn.close()

if __name__ == "__main__":
    asyncio.run(main())