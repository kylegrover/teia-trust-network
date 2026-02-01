import asyncio
import httpx
import sqlite3
import json
import logging
import random
import datetime
from email.utils import parsedate_to_datetime
from typing import Optional, Dict, Any

# --- CONFIG ---
DB_FILE = "teia_index.db"
BATCH_SIZE = 50       # How many items to fetch in parallel
MAX_RETRIES = 3       # How many times to retry a specific token before marking FAILED
CONCURRENCY = 10      # Simultaneous HTTP requests

# Public IPFS Gateways (We rotate these to avoid rate limits)
GATEWAYS = [
    "https://ipfs.io/ipfs/",
    "https://cloudflare-ipfs.com/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
    "https://dweb.link/ipfs/",
]

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("worker")

def get_db():
    return sqlite3.connect(DB_FILE, timeout=30.0)

async def fetch_ipfs_json(client: httpx.AsyncClient, uri: str) -> Optional[Dict[str, Any]]:
    """Fetch JSON metadata for an IPFS CID using multiple gateways.

    Improvements over the original:
    - Honors `MAX_RETRIES` and uses exponential backoff + jitter
    - Respects `Retry-After` header on 429 responses (both seconds and HTTP-date)
    - Handles TooManyRedirects and logs redirect history when present
    - Sets `Accept: application/json` to reduce HTML error pages
    """
    if not uri or len(uri) < 5:
        return None

    cid = uri.replace("ipfs://", "").strip()
    selected_gateways = random.sample(GATEWAYS, len(GATEWAYS))

    for gateway in selected_gateways:
        url = f"{gateway}{cid}"
        attempt = 0
        backoff = 1.0
        last_was_429 = False

        while attempt < MAX_RETRIES:
            try:
                r = await client.get(url, timeout=10.0, follow_redirects=True, headers={"Accept": "application/json"})

                # Successful JSON
                if r.status_code == 200:
                    # If the gateway returned redirects before the final response, log that (helpful for debugging)
                    if getattr(r, "history", None):
                        logger.debug("%s redirected %d time(s) when fetching %s", gateway, len(r.history), cid)

                    try:
                        return r.json()
                    except json.JSONDecodeError:
                        # Gateway sometimes returns HTML-based error pages with 200
                        logger.debug("%s returned non-JSON 200 for %s", gateway, cid)
                        return None

                # Rate limited: respect Retry-After header when present and retry with backoff
                if r.status_code == 429:
                    last_was_429 = True
                    ra = r.headers.get("Retry-After")
                    sleep_for = None

                    if ra:
                        # Retry-After can be seconds or an HTTP-date
                        try:
                            sleep_for = int(ra)
                        except ValueError:
                            try:
                                dt = parsedate_to_datetime(ra)
                                # convert to UTC and compute seconds
                                sleep_for = max(0, (dt - datetime.datetime.utcnow()).total_seconds())
                            except Exception:
                                sleep_for = None

                    if sleep_for is None:
                        sleep_for = backoff + random.random() * 0.5

                    logger.warning("%s -> 429 for %s (attempt %d/%d). sleeping %.1fs", gateway, cid, attempt + 1, MAX_RETRIES, sleep_for)
                    await asyncio.sleep(sleep_for)
                    attempt += 1
                    backoff *= 2
                    continue

                # Unexpected 3xx/4xx/5xx: don't hammer same gateway — try next gateway
                if 300 <= r.status_code < 600:
                    logger.debug("%s returned %d for %s; skipping gateway", gateway, r.status_code, cid)
                    break

            except httpx.TooManyRedirects:
                logger.warning("Too many redirects from %s when fetching %s", gateway, cid)
                break
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                # transient network error -> retry same gateway with backoff
                logger.debug("connect/timeout from %s for %s: %s (attempt %d/%d)", gateway, cid, e, attempt + 1, MAX_RETRIES)
                attempt += 1
                await asyncio.sleep(backoff + random.random() * 0.2)
                backoff *= 2
                continue
            except Exception as e:
                logger.exception("Unexpected error fetching %s from %s: %s", cid, gateway, e)
                break

        # If gateway returned repeated 429s, give a slightly longer cooldown before trying the next gateway
        if last_was_429:
            await asyncio.sleep(0.5)

    return None

async def process_batch(client: httpx.AsyncClient):
    """
    Selects a batch of 'Unknown' tokens and updates them.
    """
    conn = get_db()
    c = conn.cursor()
    
    # 1. Select candidates
    # We look for tokens that are 'Unknown' AND haven't been marked 'FAILED'
    c.execute("""
        SELECT id, metadata_uri FROM tokens 
        WHERE title = 'Unknown' 
        LIMIT ?
    """, (BATCH_SIZE,))
    
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        return 0

    updates = []
    
    async def process_single(row):
        tid, uri = row
        
        # If no URI exists, mark as invalid
        if not uri or uri == "Unknown":
            return (tid, "MISSING_URI", "MISSING_URI", "MISSING_URI", 0)

        data = await fetch_ipfs_json(client, uri)
        
        if data:
            # --- PARSE METADATA ---
            # Title
            title = data.get("name", "Untitled").replace("\x00", "") # Clean null bytes
            
            # Creator (Minter)
            # Try 'creators' array first (Teia/HEN v2), then 'issuer' (HEN v1)
            creators = data.get("creators", [])
            minter = "Unknown"
            if isinstance(creators, list) and len(creators) > 0:
                minter = creators[0]
            elif "issuer" in data:
                minter = data.get("issuer")
            
            # Artifact (The image/video)
            artifact = data.get("artifactUri", data.get("displayUri", ""))
            
            # Royalties (Often hidden in formats or top level)
            # This is imprecise in JSON, but good enough for display
            royalties = 0
            if "royalties" in data:
                try:
                    r = data["royalties"]
                    if isinstance(r, dict):
                        # standard TZIP format: { decimals: 3, shares: { addr: 100 } }
                        shares = r.get("shares", {})
                        if shares:
                            royalties = sum(shares.values()) / (10 ** r.get("decimals", 0)) * 100
                except: pass
            
            return (tid, title[:100], minter, artifact, int(royalties))
        else:
            # Could not fetch after all attempts
            return (tid, "FAILED", "FAILED", "FAILED", 0)

    # 2. Run fetches in parallel
    tasks = [process_single(row) for row in rows]
    results = await asyncio.gather(*tasks)
    
    # 3. Write to DB
    conn = get_db()
    success_count = 0
    
    # Filter out None results
    valid_results = [r for r in results if r is not None]
    
    for res in valid_results:
        tid, title, minter, artifact, royalties = res
        if title != "FAILED":
            # Success: Update real data
            conn.execute("""
                UPDATE tokens 
                SET title = ?, minter = ?, artifact_uri = ?, royalties = ? 
                WHERE id = ?
            """, (title, minter, artifact, royalties, tid))
            success_count += 1
        else:
            # Failure: Mark as FAILED so we don't retry immediately
            # (You can manually reset these to 'Unknown' later if you want to retry)
            conn.execute("UPDATE tokens SET title = 'FAILED' WHERE id = ?", (tid,))
            
    conn.commit()
    conn.close()
    
    return len(rows)

async def main():
    print("🚀 Starting Metadata Worker...")
    print("   (Press Ctrl+C to stop. Progress is saved automatically.)")
    
    # Initialize connection pool settings
    limits = httpx.Limits(max_keepalive_connections=CONCURRENCY, max_connections=CONCURRENCY)
    
    async with httpx.AsyncClient(limits=limits, timeout=15.0) as client:
        total_processed = 0
        while True:
            count = await process_batch(client)
            
            if count == 0:
                print("💤 No more 'Unknown' tokens found. Sleeping 30s...")
                await asyncio.sleep(30)
            else:
                total_processed += count
                print(f"✅ Processed batch. Total this session: {total_processed}", end="\r")
                # Tiny sleep to let the CPU breathe
                await asyncio.sleep(0.5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Worker stopped.")