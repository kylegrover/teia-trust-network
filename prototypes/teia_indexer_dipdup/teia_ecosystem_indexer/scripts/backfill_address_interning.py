"""Utility: run the SQLite backfill locally (dev).
Usage: python scripts/backfill_address_interning.py --db teia_trust.sqlite3

This script is intentionally small and uses stdlib `sqlite3` for local dev only.
For Postgres, apply `sql/on_reindex/0001_address_interning.postgres.sql` with psql.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

# Resolve SQL path relative to this script (robust when running from other CWDs)
SQL_PATH = Path(__file__).resolve().parents[1] / 'sql' / 'on_reindex' / '0001_address_interning.sqlite.sql'
if not SQL_PATH.exists():
    raise SystemExit(f'Backfill SQL not found at {SQL_PATH!s}. Run from project root or adjust path.')
with SQL_PATH.open('r', encoding='utf-8') as _fh:
    SQL = _fh.read()


def run(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        print('Running backfill SQL against:', db_path)
        conn.executescript(SQL)
        conn.commit()
        print(f"Backfill complete — verify with: sqlite3 {db_path} 'SELECT count(*) FROM holder;'")
    finally:
        conn.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--db', required=True, help='Path to SQLite DB file (dev)')
    args = p.parse_args()
    run(args.db)
