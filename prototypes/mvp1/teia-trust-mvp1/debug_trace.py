# debug_trace.py
import httpx
import asyncio
import json

# Teia Marketplace Contract
TEIA_MARKET = "KT1PHubm9HtyQEJ4BBpMTVomq6mhbfNZ9z5w"

async def trace_single_event():
    async with httpx.AsyncClient() as client:
        print("\n🔎 --- STEP 1: Find a recent Collect ---")
        # 1. Get just ONE collect operation
        r = await client.get(
            "https://api.tzkt.io/v1/operations/transactions",
            params={
                "target": TEIA_MARKET,
                "entrypoint": "collect",
                "status": "applied",
                "limit": 1
            }
        )
        collect = r.json()[0]
        op_hash = collect['hash']
        print(f"User:   {collect['sender']['address']}")
        print(f"Hash:   {op_hash}")
        print(f"Op ID:  {collect['id']} (This is the Parent)")

        print(f"\n🔎 --- STEP 2: Get ALL Internal Ops in this Group ---")
        # 2. Get the full execution trace for this hash
        r = await client.get(
            "https://api.tzkt.io/v1/operations/transactions",
            params={"hash": op_hash}
        )
        ops = r.json()
        
        all_ids = []
        for op in ops:
            # Safe access to fields
            entrypoint = op.get('parameter', {}).get('entrypoint', 'default/transfer')
            target_alias = op.get('target', {}).get('alias', 'Unknown')
            target_addr = op.get('target', {}).get('address')
            
            print(f" > Found Op ID: {op['id']}")
            print(f"   Action:      {entrypoint} -> {target_alias} ({target_addr})")
            
            all_ids.append(op['id'])

        print(f"\n🔎 --- STEP 3: Check for Transfers on these IDs ---")
        # 3. Check which ID actually owns the transfer
        r = await client.get(
            "https://api.tzkt.io/v1/tokens/transfers",
            params={
                "transactionId.in": ",".join(map(str, all_ids))
            }
        )
        transfers = r.json()
        
        if len(transfers) == 0:
            print("❌ NO TRANSFERS FOUND linked to these IDs.")
            print("   Debug: Checking if transfers exist for this Level/Block instead...")
            
            # Fallback: Find the transfer by brute force (Block + Recipient) 
            # to see what ID it *claims* to have.
            r_fallback = await client.get(
                "https://api.tzkt.io/v1/tokens/transfers",
                params={"level": collect['level']}
            )
            
            found_any = False
            for t in r_fallback.json():
                # Check if this transfer went to our User
                if t.get('to', {}).get('address') == collect['sender']['address']:
                    found_any = True
                    print(f"   -> FOUND ORPHAN TRANSFER!")
                    print(f"      It claims its transactionId is: {t.get('transactionId')}")
                    print(f"      Is that in our list? {t.get('transactionId') in all_ids}")
            
            if not found_any:
                print("   ❌ No transfers found for this user in this block at all. (Maybe a swap/offer cancellation?)")

        else:
            for t in transfers:
                print(f"✅ SUCCESS! Found Transfer:")
                print(f"   Token ID: {t.get('token', {}).get('tokenId')}")
                print(f"   Artist:   {t.get('token', {}).get('metadata', {}).get('creators', ['Unknown'])[0]}")
                print(f"   Linked to Transaction ID: {t.get('transactionId')}")

if __name__ == "__main__":
    asyncio.run(trace_single_event())