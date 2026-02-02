"""Benchmark several Teia SQLite DBs and produce a concise report.

Usage (WSL):
  ./.venv/bin/python scripts/benchmark_sqlite_dbs.py \
    --dbs db_backups/teia_ecosystem.sqlite3 db_backups/teia_ecosystem_backfilled.sqlite3 db_backups/teia_ecosystem_backup_commit_84825d.sqlite3 \
    --address tz1... --vacuum

What it does:
- For each DB: reports file bytes (precise via PRAGMA), row counts, distinct address counts, freelist_count, index list.
- Optionally VACUUMs a temporary copy (won't overwrite originals unless --overwrite).
- Picks a heavy address (or uses --address) and runs timed lookups for both legacy string and interned-FK paths (median of several runs).
- Emits human summary to stdout and writes JSON to `bench_report-<ts>.json`.

Notes:
- The script does not require the sqlite3 CLI; it uses Python's sqlite3 module.
- Default DBs point to the `db_backups/` names you provided.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import statistics
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_DBS = [
    "db_backups/teia_ecosystem.sqlite3",
    "db_backups/teia_ecosystem_backfilled.sqlite3",
    "db_backups/teia_ecosystem_backup_commit_84825d.sqlite3",
]


def human(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024.0:
            return f"{n:3.1f}{u}"
        n /= 1024.0
    return f"{n:.1f}TB"


def open_conn(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def db_bytes(conn: sqlite3.Connection) -> int:
    pc = conn.execute("PRAGMA page_count;").fetchone()[0]
    ps = conn.execute("PRAGMA page_size;").fetchone()[0]
    return int(pc) * int(ps)


def vacuum_copy(orig_path: Path, overwrite: bool = False) -> Path:
    """Create a temporary copy of orig_path, VACUUM it, and return the path.
    If overwrite=True, VACUUMs the original file in place (dangerous).
    """
    if overwrite:
        conn = open_conn(str(orig_path))
        try:
            conn.execute("VACUUM;")
            conn.commit()
        finally:
            conn.close()
        return orig_path

    tmpdir = Path(tempfile.mkdtemp(prefix="teia_vac_"))
    dst = tmpdir / orig_path.name
    shutil.copy2(orig_path, dst)
    conn = open_conn(str(dst))
    try:
        conn.execute("VACUUM;")
        conn.commit()
    finally:
        conn.close()
    return dst


def pick_heavy_address(conn: sqlite3.Connection) -> Optional[str]:
    """Try multiple high-frequency sources to find a heavy address for benchmarking."""
    candidates = [
        ("swap", "seller_address"),
        ("trade", "buyer_address"),
        ("token", "creator_address"),
        ("trustedge", "buyer_address"),
        ("trustedge", "seller_address"),
    ]
    for table, col in candidates:
        try:
            q = f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL GROUP BY {col} ORDER BY COUNT(*) DESC LIMIT 1;"
            row = conn.execute(q).fetchone()
            if row and row[0]:
                return row[0]
        except sqlite3.Error:
            continue
    return None


def timed_query(conn: sqlite3.Connection, sql: str, params: Tuple = (), runs: int = 5) -> Dict[str, Any]:
    times: List[float] = []
    result_count = None
    cur = conn.cursor()
    for _ in range(runs):
        t0 = time.perf_counter()
        cur.execute(sql, params)
        r = cur.fetchone()
        t = time.perf_counter() - t0
        times.append(t)
        if result_count is None:
            result_count = r[0] if r is not None else None
    return {
        "runs": runs,
        "median_s": statistics.median(times) if times else None,
        "mean_s": statistics.mean(times) if times else None,
        "min_s": min(times) if times else None,
        "max_s": max(times) if times else None,
        "result_count": result_count,
    }


def gather_indexes(conn: sqlite3.Connection, table: str = "swap") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        idxs = conn.execute(f"PRAGMA index_list('{table}');").fetchall()
    except sqlite3.Error:
        return out
    for idx in idxs:
        name = idx[1]
        detail = conn.execute(f"PRAGMA index_info('{name}');").fetchall()
        out.append({"name": name, "unique": bool(idx[2]), "columns": [d[2] for d in detail]})
    return out


def gather_basic(conn: sqlite3.Connection) -> Dict[str, Any]:
    def safe_one(q: str):
        try:
            return conn.execute(q).fetchone()[0]
        except sqlite3.Error:
            return None

    # also capture token/trustedge presence (they commonly hold addresses)
    return {
        "tables": [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()],
        "swap_count": safe_one("SELECT count(*) FROM swap"),
        "trade_count": safe_one("SELECT count(*) FROM trade"),
        "token_count": safe_one("SELECT count(*) FROM token"),
        "trustedge_count": safe_one("SELECT count(*) FROM trustedge"),
        "holder_count": safe_one("SELECT count(*) FROM holder"),
        "distinct_seller_addresses": safe_one(
            "SELECT COUNT(DISTINCT seller_address) FROM swap WHERE seller_address IS NOT NULL"
        ),
        "swap_missing_seller_id": safe_one("SELECT count(*) FROM swap WHERE seller_id IS NULL"),
        "avg_seller_address_len": safe_one("SELECT avg(length(seller_address)) FROM swap WHERE seller_address IS NOT NULL"),
        "freelist_count": safe_one("PRAGMA freelist_count;"),
    }


def gather_for_db(path: Path, do_vacuum: bool = False, overwrite_vacuum: bool = False, address: Optional[str] = None) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    report: Dict[str, Any] = {"path": str(path), "timestamp": datetime.utcnow().isoformat()}

    working_path = path
    # run VACUUM on a temp copy (unless overwrite requested)
    if do_vacuum:
        vac_path = vacuum_copy(path, overwrite=overwrite_vacuum)
        report["vacuumed_path"] = str(vac_path)
        working_path = vac_path

    conn = open_conn(str(working_path))
    try:
        report["bytes"] = db_bytes(conn)
        report.update(gather_basic(conn))
        report["indexes"] = gather_indexes(conn, table="swap")

        heavy = address or pick_heavy_address(conn)
        report["heavy_address"] = heavy

        # show schema for the most relevant tables so we can see which columns are populated
        def table_info(t: str):
            try:
                return conn.execute(f"PRAGMA table_info('{t}')").fetchall()
            except sqlite3.Error:
                return []

        report["table_info_swap"] = table_info('swap')
        report["table_info_token"] = table_info('token')

        # sample rows for quick inspection (non-exhaustive)
        def sample(t: str, n: int = 3):
            try:
                return [dict(r) for r in conn.execute(f"SELECT * FROM {t} LIMIT {n}").fetchall()]
            except sqlite3.Error:
                return []

        report["sample_swap"] = sample('swap', 5)
        report["sample_token"] = sample('token', 5)
        report["sample_holder"] = sample('holder', 5)

        if heavy:
            # try legacy and interned lookups even if swap may be empty — fallback queries included
            legacy_sql = "SELECT COUNT(*) FROM swap WHERE seller_address=?"
            intern_sql = "SELECT COUNT(*) FROM swap WHERE seller_id=(SELECT id FROM holder WHERE address=?)"
            token_legacy_sql = "SELECT COUNT(*) FROM token WHERE creator_address=?"

            report["bench_legacy"] = timed_query(conn, legacy_sql, (heavy,))
            report["bench_interned"] = timed_query(conn, intern_sql, (heavy,))
            report["bench_token_legacy"] = timed_query(conn, token_legacy_sql, (heavy,))

            report["explain_legacy"] = conn.execute("EXPLAIN QUERY PLAN SELECT COUNT(*) FROM swap WHERE seller_address=?", (heavy,)).fetchall()
            report["explain_interned"] = conn.execute(
                "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM swap WHERE seller_id=(SELECT id FROM holder WHERE address=?)",
                (heavy,),
            ).fetchall()
            report["explain_token_legacy"] = conn.execute("EXPLAIN QUERY PLAN SELECT COUNT(*) FROM token WHERE creator_address=?", (heavy,)).fetchall()
    finally:
        conn.close()

    return report


def summary_report(reports: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("DB benchmark summary:")
    header = (
        f"{'db':36} {'bytes':>10} {'swap':>8} {'token':>8} {'holders':>8} {'distinct_addrs':>13} {'missing_seller_id':>18} {'median_legacy_ms':>15} {'median_intern_ms':>15} {'note':>8}"
    )
    lines.append(header)
    lines.append('-' * len(header))
    for r in reports:
        dbn = Path(r['path']).name[:36]
        bytes_h = human(r.get('bytes', 0) or 0)
        swap = r.get('swap_count') or 0
        token = r.get('token_count') or 0
        holders = r.get('holder_count') or 0
        distinct = r.get('distinct_seller_addresses') or 0
        missing = r.get('swap_missing_seller_id') or 0
        legacy_ms = (r.get('bench_legacy') or {}).get('median_s')
        intern_ms = (r.get('bench_interned') or {}).get('median_s')
        legacy_ms_s = f"{legacy_ms*1000:6.1f}" if legacy_ms else '  n/a'
        intern_ms_s = f"{intern_ms*1000:6.1f}" if intern_ms else '  n/a'
        # quick heuristic note
        if holders > 0 and swap == 0 and token > 0:
            note = 'holders←token'
        elif holders > 0 and swap == 0 and token == 0:
            note = 'holders_only?'
        else:
            note = ''
        lines.append(
            f"{dbn:36} {bytes_h:>10} {swap:8,d} {token:8,d} {holders:8,d} {distinct:13,d} {missing:18,d} {legacy_ms_s:>15} {intern_ms_s:>15} {note:>8}"
        )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dbs", nargs='+', default=DEFAULT_DBS, help="Paths to SQLite DB files to benchmark")
    p.add_argument("--address", help="Address to use for micro-benchmarks (auto-picked if omitted)")
    p.add_argument("--vacuum", action='store_true', help="Run VACUUM on a temporary copy and report vacuumed size")
    p.add_argument("--overwrite-vacuum", action='store_true', help="VACUUM the original DB(s) in-place (dangerous)")
    p.add_argument("--out", help="Write full JSON report to this path")
    args = p.parse_args(argv)

    reports: List[Dict[str, Any]] = []
    for db in args.dbs:
        path = Path(db)
        try:
            rep = gather_for_db(path, do_vacuum=args.vacuum, overwrite_vacuum=args.overwrite_vacuum, address=args.address)
            reports.append(rep)
        except Exception as e:
            reports.append({"path": str(path), "error": str(e)})

    print(summary_report(reports))
    out = args.out or f"bench_report-{int(time.time())}.json"
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump({"generated_at": datetime.utcnow().isoformat(), "reports": reports}, fh, indent=2, default=str)
    print(f"\nFull JSON report written to: {out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
