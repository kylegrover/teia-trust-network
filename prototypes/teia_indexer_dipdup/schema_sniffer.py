import json
import urllib.request
import time
from datetime import datetime

# --- CONFIGURATION ---
CONTRACTS = {
    "HEN_V1_MARKET": "KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton",
    "HEN_V2_MARKET": "KT1HbQepzV1nVGg8QVznG7z4RcHseD5kwqBn",
    "TEIA_MARKET":   "KT1PHubm9HtyQEJ4BBpMTVomq6mhbfNZ9z5w",
    "OBJKT_MINTER":  "KT1Hkg5qeNhfwpKW4fXvq7HGZB9z2EnmCCA9" # The Token Registry
}

# The specific actions we care about for the Trust Graph
INTERESTING_ENTRYPOINTS = ["collect", "swap", "mint", "cancel_swap"]

def fetch_json(url):
    """Helper to fetch JSON from TzKT with a small delay to be polite."""
    time.sleep(0.1) 
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                return {"error": f"Status {response.status}"}
            return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e)}

def print_section(title):
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def analyze_contract(name, address):
    print_section(f"ANALYZING: {name} ({address})")
    
    # 1. Fetch Entrypoints (The Schema)
    print(f"🔍 Fetching Entrypoint Schemas...")
    entrypoints = fetch_json(f"https://api.tzkt.io/v1/contracts/{address}/entrypoints")
    
    found_eps = []
    for ep in entrypoints:
        if ep['name'] in INTERESTING_ENTRYPOINTS:
            found_eps.append(ep['name'])
            print(f"\n  [Entrypoint: {ep['name']}]")
            print(f"  Signature: {json.dumps(ep['jsonParameters'], indent=2)}")
            
            # 2. Fetch Real Examples (The Data)
            # Get the last 2 successful transactions for this entrypoint
            print(f"  👉 Fetching real examples for '{ep['name']}'...")
            ops = fetch_json(
                f"https://api.tzkt.io/v1/operations/transactions?"
                f"target={address}&entrypoint={ep['name']}&status=applied&limit=2"
            )
            
            if ops and not isinstance(ops, dict):
                for i, op in enumerate(ops):
                    val = op.get('parameter', {}).get('value')
                    print(f"     Ex {i+1}: {val}")
            else:
                print("     (No recent examples found)")

    # 3. Fetch Storage Schema (How data is stored)
    print(f"\n📦 Fetching Storage Schema...")
    storage_schema = fetch_json(f"https://api.tzkt.io/v1/contracts/{address}/storage/schema")
    print(json.dumps(storage_schema, indent=2))

def main():
    print(f"Starting Teia/HEN Schema Sniffer at {datetime.now()}")
    
    for name, address in CONTRACTS.items():
        analyze_contract(name, address)
        
    print_section("DONE")

if __name__ == "__main__":
    main()