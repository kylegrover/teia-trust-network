import requests
import json
import asyncio
import aiohttp
from typing import Dict, List

CONTRACTS = {
    "hen_objkts": "KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton",
    "hen_minter_v1": "KT1Hkg5qeNhfwpKW4fXvq7HGZB9z2EnmCCA9",
    "hen_market_v2": "KT1HbQepzV1nVGg8QVznG7z4RcHseD5kwqBn",
    "teia_market": "KT1PHubm9HtyQEJ4BBpMTVomq6mhbfNZ9z5w",
    "hen_subjkts": "KT1My1wDZHDGweCrJnQJi3wcFaS67iksirvj",
}

TZKT_API = "https://api.tzkt.io/v1"

async def fetch_json(session: aiohttp.ClientSession, url: str):
    async with session.get(url) as response:
        if response.status == 200:
            return await response.json()
        return None

async def inspect_contract(session: aiohttp.ClientSession, name: str, address: str):
    print(f"\n{'='*80}")
    print(f"Inspecting {name} ({address})")
    print(f"{'='*80}")

    # 1. Get Storage Schema
    storage = await fetch_json(session, f"{TZKT_API}/contracts/{address}/storage")
    print("\n[STORAGE EXAMPLE]")
    print(json.dumps(storage, indent=2)[:1000] + ("..." if len(json.dumps(storage)) > 1000 else ""))

    # 2. Get Big Maps
    bigmaps = await fetch_json(session, f"{TZKT_API}/contracts/{address}/bigmaps")
    print("\n[BIG MAPS]")
    if bigmaps:
        for bm in bigmaps:
            print(f"- ID {bm.get('ptr')}: {bm.get('path')} (key: {bm.get('keyType', {}).get('prim')}, value: {bm.get('valueType', {}).get('prim')})")
    else:
        print("No big maps found.")

    # 3. Get Entrypoints
    entrypoints = await fetch_json(session, f"{TZKT_API}/contracts/{address}/entrypoints")
    print("\n[ENTRYPOINTS]")
    if entrypoints:
        for ep in entrypoints:
            print(f"- {ep.get('name')}")
    
    # 4. Get a sample transaction for key entrypoints
    # (Checking collect/swap/mint shapes)
    sample_ops = await fetch_json(session, f"{TZKT_API}/operations/transactions?target={address}&limit=1&status=applied")
    if sample_ops:
        print("\n[SAMPLE TRANSACTION PARAMETER]")
        op = sample_ops[0]
        print(f"Entrypoint: {op.get('parameter', {}).get('entrypoint')}")
        print(json.dumps(op.get('parameter', {}).get('value'), indent=2))

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [inspect_contract(session, name, addr) for name, addr in CONTRACTS.items()]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
