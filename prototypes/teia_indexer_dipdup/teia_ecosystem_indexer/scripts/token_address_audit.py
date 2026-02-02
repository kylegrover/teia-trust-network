"""Quick audit for address-origin in the DB (tokens → holders).

Purpose: run the three checks you asked for and print a short, human-friendly report:
  - token counts, distinct creator addresses, avg creator-address length
  - top-N creator addresses (frequency)
  - holder counts and token->holder join coverage
  - index presence for `swap` and `holder`

Usage (repo venv, WSL):
  ./.venv/bin/python scripts/token_address_audit.py --db db_backups/teia_ecosystem.sqlite3 --top 20

Output: plain text summary suitable for quick interpretation and copy/paste into a bug report.
"""
from __future__ import annotations
import argparse
import sqlite3
from pathlib import Path
from typing import Iterable, List, Tuple


def open_conn(db: Path) -> sqlite3.Connection:
    if not db.exists():
        raise SystemExit(f"DB not found: {db}")
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def one(conn: sqlite3.Connection, q: str):
    try:
        return conn.execute(q).fetchone()[0]
    except Exception:
        return None


def top_creators(conn: sqlite3.Connection, limit: int) -> List[Tuple[str, int]]:
    try:
        cur = conn.execute(
            "SELECT creator_address AS addr, COUNT(*) AS cnt FROM token WHERE creator_address IS NOT NULL GROUP BY addr ORDER BY cnt DESC LIMIT ?",
            (limit,),
        )
        return [(r[0], int(r[1])) for r in cur.fetchall()]
    except Exception:
        return []


def index_list(conn: sqlite3.Connection, table: str) -> List[sqlite3.Row]:
    try:
        return conn.execute(f"PRAGMA index_list('{table}')").fetchall()
    except Exception:
        return []


def run_audit(db_path: Path, top_n: int) -> None:
    conn = open_conn(db_path)
    try:
        print(f"DB: {db_path} (size approx: {db_path.stat().st_size / 1024**2:.1f} MB)")
        print("—" * 72)
        print("Counts & coverage:")
        print("  token_count:", one(conn, "SELECT count(*) FROM token"))
        print("  distinct_creator_addresses:", one(conn, "SELECT COUNT(DISTINCT creator_address) FROM token WHERE creator_address IS NOT NULL"))
        print("  avg_creator_address_length:", one(conn, "SELECT avg(length(creator_address)) FROM token WHERE creator_address IS NOT NULL"))
        print("  holder_count:", one(conn, "SELECT count(*) FROM holder"))
        print("  token.creator_id populated:", one(conn, "SELECT count(*) FROM token WHERE creator_id IS NOT NULL"))
        print("  token JOIN holder (matches):", one(conn, "SELECT count(*) FROM token t JOIN holder h ON h.address = t.creator_address"))
        print()

        print(f"Top {top_n} creators (address — occurrences):")
        for addr, cnt in top_creators(conn, top_n):
            print(f"  {addr:36}  {cnt:6,d}")
        if not top_creators(conn, top_n):
            print("  (no creators found / table empty)")
        print()

        print("Indexes (swap, holder):")
        for t in ("swap", "holder", "token"):
            idxs = index_list(conn, t)
            if not idxs:
                print(f"  {t}: (no indexes or table missing)")
                continue
            print(f"  {t}:")
            for idx in idxs:
                name = idx[1]
                unique = bool(idx[2])
                cols = [c[2] for c in conn.execute(f"PRAGMA index_info('{name}')").fetchall()]
                print(f"    - {name} (unique={unique}) cols={cols}")
        print()

        print("Samples (token, holder) — first 3 rows each:")
        def sample(table: str, n: int = 3):
            try:
                rows = conn.execute(f"SELECT * FROM {table} LIMIT {n}").fetchall()
                return rows
            except Exception:
                return []
        for t in ("token", "holder"):
            rows = sample(t, 3)
            print(f"  {t} ({len(rows)} rows):")
            for r in rows:
                # show only address-related columns to keep output small
                d = {k: r[k] for k in r.keys() if 'address' in k or 'id' in k or 'token_id' in k}
                print(f"    {d}")
        print("\nDone — interpret: if token_count >> distinct_creator_addresses then interning will save space.")
    finally:
        conn.close()


def main(argv: Iterable[str] | None = None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--db', default='db_backups/teia_ecosystem.sqlite3', help='SQLite DB to inspect')
    p.add_argument('--top', type=int, default=20, help='Top-N creator addresses')
    args = p.parse_args(list(argv) if argv else None)
    run_audit(Path(args.db), args.top)


if __name__ == '__main__':
    main()
