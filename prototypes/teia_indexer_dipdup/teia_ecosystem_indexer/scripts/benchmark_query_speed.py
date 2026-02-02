
import sqlite3
import time
import statistics
from pathlib import Path
from typing import Dict, List, Any

# Paths to the databases
DB_NEW = Path("teia_ecosystem.sqlite3")
DB_OLD = Path("db_backups/teia_ecosystem_backup_commit_848425d.sqlite3")

def get_top_wallets(db_path: Path, limit: int = 5) -> List[str]:
    """Find the most active wallets to use for benchmarking."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    # Check which table to use based on DB version
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    
    if "token" in tables:
        # In old DB, creator_address is a string. In new DB, it might be gone.
        # Let's try to find a shared way or just hardcode some known active ones if possible.
        # For now, let's just grab from the old DB's token table.
        try:
            res = conn.execute("SELECT creator_address FROM token WHERE creator_address IS NOT NULL GROUP BY creator_address ORDER BY COUNT(*) DESC LIMIT ?", (limit,)).fetchall()
            return [r[0] for r in res]
        except:
            return []
    return []

def bench_query_old(conn: sqlite3.Connection, address: str) -> float:
    """Benchmark: Get all trades and swaps for an address in the OLD schema."""
    t0 = time.perf_counter()
    # Simple string-based lookups
    conn.execute("SELECT * FROM swap WHERE seller_address = ?", (address,)).fetchall()
    conn.execute("SELECT * FROM trade WHERE buyer_address = ?", (address,)).fetchall()
    # Join example
    conn.execute("""
        SELECT t.*, s.price_mutez 
        FROM trade t 
        JOIN swap s ON t.swap_id = s.id 
        WHERE t.buyer_address = ?
    """, (address,)).fetchall()
    return time.perf_counter() - t0

def bench_query_new(conn: sqlite3.Connection, address: str) -> float:
    """Benchmark: Get all trades and swaps for an address in the NEW schema."""
    t0 = time.perf_counter()
    # 1. First hop: string -> ID
    holder = conn.execute("SELECT id FROM holder WHERE address = ?", (address,)).fetchone()
    if holder:
        h_id = holder[0]
        # 2. Subsequent lookups use the INT ID
        conn.execute("SELECT * FROM swap WHERE seller_id = ?", (h_id,)).fetchall()
        conn.execute("SELECT * FROM trade WHERE buyer_id = ?", (h_id,)).fetchall()
        # 3. Join example (ID based)
        conn.execute("""
            SELECT t.*, s.price_mutez 
            FROM trade t 
            JOIN swap s ON t.swap_id = s.id 
            WHERE t.buyer_id = ?
        """, (h_id,)).fetchall()
    return time.perf_counter() - t0

def bench_aggregation_old(conn: sqlite3.Connection) -> float:
    """Heavy aggregation on strings."""
    t0 = time.perf_counter()
    conn.execute("SELECT creator_address, COUNT(*) FROM token GROUP BY creator_address").fetchall()
    return time.perf_counter() - t0

def bench_aggregation_new(conn: sqlite3.Connection) -> float:
    """Heavy aggregation on integers."""
    t0 = time.perf_counter()
    conn.execute("SELECT creator_id, COUNT(*) FROM token GROUP BY creator_id").fetchall()
    return time.perf_counter() - t0

def run_benchmark():
    if not DB_NEW.exists() or not DB_OLD.exists():
        print(f"Error: Ensure both {DB_NEW} and {DB_OLD} exist.")
        return

    print(f"--- Benchmarking Address Interning ---")
    print(f"Old DB: {DB_OLD} ({DB_OLD.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"New DB: {DB_NEW} ({DB_NEW.stat().st_size / 1024 / 1024:.2f} MB)")
    
    addresses = get_top_wallets(DB_OLD)
    if not addresses:
        print("No addresses found to benchmark.")
        return

    conn_old = sqlite3.connect(DB_OLD)
    conn_new = sqlite3.connect(DB_NEW)
    
    # Warm up caches
    for addr in addresses:
        bench_query_old(conn_old, addr)
        bench_query_new(conn_new, addr)
    bench_aggregation_old(conn_old)
    bench_aggregation_new(conn_new)

    results_old = []
    results_new = []
    agg_old = []
    agg_new = []
    iterations = 50

    print(f"\nRunning {iterations} iterations for Point Queries...")
    for addr in addresses:
        for _ in range(iterations):
            results_old.append(bench_query_old(conn_old, addr))
            results_new.append(bench_query_new(conn_new, addr))

    print(f"Running 10 iterations for Aggregation (GROUP BY)...")
    for _ in range(10):
        agg_old.append(bench_aggregation_old(conn_old))
        agg_new.append(bench_aggregation_new(conn_new))

    print("\n--- RESULTS ---")
    print(f"Point Query (Median):")
    print(f"  Old (Strings): {statistics.median(results_old)*1000:.4f} ms")
    print(f"  New (IDs):     {statistics.median(results_new)*1000:.4f} ms")
    
    print(f"\nAggregation (Median):")
    print(f"  Old (Strings): {statistics.median(agg_old)*1000:.4f} ms")
    print(f"  New (IDs):     {statistics.median(agg_new)*1000:.4f} ms")
    
    agg_diff = (statistics.median(agg_new) - statistics.median(agg_old)) / statistics.median(agg_old) * 100
    print(f"\nAggregation Improvement: {abs(agg_diff):.1f}% {'FASTER' if agg_diff < 0 else 'SLOWER'}")

    print("\n--- SUMMARY ---")
    print(f"Storage Savings: {((DB_OLD.stat().st_size - DB_NEW.stat().st_size) / DB_OLD.stat().st_size * 100):.1f}%")


if __name__ == "__main__":
    run_benchmark()
