# check_progress.py
import httpx
from database import get_db

async def check():
    db = get_db()
    local_id = db["state"].get("last_processed_id")["value"]
    
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.tzkt.io/v1/operations/transactions?limit=1&sort.desc=id&select=id")
        network_id = r.json()[0]
        
    gap = network_id - local_id
    print(f"📊 Progress: {local_id} / {network_id}")
    if gap > 1000:
        print(f"🏃 Still syncing. {gap} operations remaining to reach real-time.")
    else:
        print("✅ You are basically at the tip!")

import asyncio
asyncio.run(check())