"""Run a safe address-interning trial on a SQLite dump (non-destructive by default).

What this script does (safe default):
- Copies the source DB into a working folder (baseline and trial copies).
- Optionally VACUUMs copies (on temp copies) to normalize sizes.
- Runs a quick benchmark (counts, distincts, index inspection, micro-query timings).
- Performs a *trial* schema change that REMOVES `token.creator_address` by creating
  a `token_new` table without that column and swapping it in the trial copy.
  (Only applied to the trial copy; original is untouched.)
- VACUUMs the trial copy, re-runs benchmarks, and prints a concise interpretation
  and JSON report with byte deltas and estimated savings.

Important safety notes:
- By default this script never mutates your provided source DB. It works on copies.
- To run destructive operations in-place you must pass `--inplace --yes-ireally-mean-it`.

Usage (WSL, repo root):
  ./.venv/bin/python scripts/run_interning_trial.py \
    --src db_backups/teia_ecosystem.sqlite3 --work-dir /tmp/teia-intern-trial --top 20 --vacuum

Exit / artifacts:
- Human summary printed to stdout.
- JSON report written to <work-dir>/interning_trial_report-<ts>.json

"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import sqlite3
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def now_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def open_conn(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    return c


def db_file_size(path: Path) -> int:
    return path.stat().st_size


def pragma_bytes(conn: sqlite3.Connection) -> int:
    pc = conn.execute("PRAGMA page_count;").fetchone()[0]
    ps = conn.execute("PRAGMA page_size;").fetchone()[0]
    return int(pc) * int(ps)


def vacuum_inplace(path: Path) -> None:
    conn = open_conn(path)
    try:
        conn.execute("VACUUM;")
        conn.commit()
    finally:
        conn.close()


def vacuum_copy(orig: Path, dst: Path) -> Path:
    shutil.copy2(orig, dst)
    vacuum_inplace(dst)
    return dst


def table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
        return [r['name'] for r in rows]
    except Exception:
        return []


def run_counts(conn: sqlite3.Connection) -> Dict[str, Any]:
    def s(q: str):
        try:
            return conn.execute(q).fetchone()[0]
        except Exception:
            return None

    return {
        'swap_count': s("SELECT count(*) FROM swap"),
        'trade_count': s("SELECT count(*) FROM trade"),
        'token_count': s("SELECT count(*) FROM token"),
        'holder_count': s("SELECT count(*) FROM holder"),
        'distinct_token_creators': s("SELECT COUNT(DISTINCT creator_address) FROM token WHERE creator_address IS NOT NULL"),
        'token_creator_id_populated': s("SELECT count(*) FROM token WHERE creator_id IS NOT NULL"),
        'token_join_holder_matches': s("SELECT count(*) FROM token t JOIN holder h ON h.address = t.creator_address"),
    }


def pick_heavy_address(conn: sqlite3.Connection) -> Optional[str]:
    candidates = [
        ("token", "creator_address"),
        ("swap", "seller_address"),
        ("trade", "buyer_address"),
        ("trustedge", "buyer_address"),
    ]
    for table, col in candidates:
        try:
            row = conn.execute(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL GROUP BY {col} ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
            if row and row[0]:
                return row[0]
        except Exception:
            continue
    return None


def timed_query(conn: sqlite3.Connection, sql: str, params: Tuple = (), runs: int = 5) -> Dict[str, Any]:
    times: List[float] = []
    result = None
    cur = conn.cursor()
    for _ in range(runs):
        t0 = time.perf_counter()
        cur.execute(sql, params)
        row = cur.fetchone()
        times.append(time.perf_counter() - t0)
        if result is None:
            result = row[0] if row is not None else None
    return {
        'runs': runs,
        'median_s': statistics.median(times) if times else None,
        'mean_s': statistics.mean(times) if times else None,
        'min_s': min(times) if times else None,
        'max_s': max(times) if times else None,
        'result_count': result,
    }


def index_list(conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
    try:
        rows = conn.execute(f"PRAGMA index_list('{table}')").fetchall()
    except Exception:
        return []
    out = []
    for r in rows:
        name = r['name']
        cols = [c[2] for c in conn.execute(f"PRAGMA index_info('{name}')").fetchall()]
        out.append({'name': name, 'unique': bool(r['unique']), 'columns': cols})
    return out


def bench_db(path: Path, vacuum: bool = False, address: Optional[str] = None) -> Dict[str, Any]:
    report: Dict[str, Any] = {'path': str(path), 'timestamp': now_ts()}
    conn = open_conn(path)
    try:
        if vacuum:
            conn.close()
            vacuum_inplace(path)
            conn = open_conn(path)
        report['file_bytes'] = db_file_size(path)
        report['pragma_bytes'] = pragma_bytes(conn)
        report.update(run_counts(conn))
        report['indexes'] = {
            'swap': index_list(conn, 'swap'),
            'token': index_list(conn, 'token'),
            'holder': index_list(conn, 'holder'),
        }
        heavy = address or pick_heavy_address(conn)
        report['heavy_address'] = heavy
        if heavy:
            report['bench_token_legacy'] = timed_query(conn, 'SELECT COUNT(*) FROM token WHERE creator_address=?', (heavy,))
            report['bench_token_interned'] = timed_query(conn, 'SELECT COUNT(*) FROM token WHERE creator_id=(SELECT id FROM holder WHERE address=?)', (heavy,))
            report['explain_token_legacy'] = conn.execute('EXPLAIN QUERY PLAN SELECT COUNT(*) FROM token WHERE creator_address=?', (heavy,)).fetchall()
            report['explain_token_interned'] = conn.execute('EXPLAIN QUERY PLAN SELECT COUNT(*) FROM token WHERE creator_id=(SELECT id FROM holder WHERE address=?)', (heavy,)).fetchall()
        # sample top creators
        try:
            report['top_creators'] = [dict(r) for r in conn.execute("SELECT creator_address AS addr, COUNT(*) AS cnt FROM token WHERE creator_address IS NOT NULL GROUP BY addr ORDER BY cnt DESC LIMIT 50").fetchall()]
        except Exception:
            report['top_creators'] = []
        # table schemas
        report['token_columns'] = table_columns(conn, 'token')
        report['holder_columns'] = table_columns(conn, 'holder')
    finally:
        conn.close()
    return report


def perform_token_drop_trial(src_path: Path, dst_path: Path) -> None:
    """On dst_path (a copy), drop token.creator_address by creating token_new without that column.
    This preserves ids and creator_id. The operation is wrapped in a transaction.
    """
    conn = open_conn(dst_path)
    try:
        cols = [c for c in table_columns(conn, 'token') if c != 'creator_address']
        if 'creator_id' not in cols:
            raise RuntimeError('creator_id is missing in token table — aborting trial')
        col_list = ', '.join(cols)
        # perform safe swap
        conn.execute('PRAGMA foreign_keys=OFF;')
        conn.execute('BEGIN;')
        # create token_new with same columns (except creator_address)
        conn.execute(f'CREATE TABLE token_new AS SELECT {col_list} FROM token;')
        conn.execute('DROP TABLE token;')
        conn.execute("ALTER TABLE token_new RENAME TO token;")
        conn.execute('COMMIT;')
        conn.execute('PRAGMA foreign_keys=ON;')
        conn.commit()
    finally:
        conn.close()


def interpret_results(base: Dict[str, Any], trial: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out['base_file_bytes'] = base.get('file_bytes')
    out['trial_file_bytes'] = trial.get('file_bytes')
    out['delta_bytes'] = (base.get('file_bytes') or 0) - (trial.get('file_bytes') or 0)
    out['delta_percent'] = ((out['delta_bytes'] / base.get('file_bytes')) * 100) if base.get('file_bytes') else None

    # theoretical string savings for token
    token_rows = base.get('token_count') or 0
    distinct_creators = base.get('distinct_token_creators') or 0
    avg_len = None
    # try to compute avg length from top creators if not available
    if base.get('top_creators'):
        # rough average: assume 36 (tezos address length) when absent
        avg_len = 36
    est_raw_savings = None
    if avg_len:
        est_raw_savings = (token_rows - distinct_creators) * avg_len
    out['est_raw_token_string_bytes_saved'] = est_raw_savings

    # practical guidance
    guidance: List[str] = []
    if (trial.get('token_count') or 0) != (base.get('token_count') or 0):
        guidance.append('ROW_COUNT_MISMATCH: token row count differs after trial — investigate')
    if (base.get('token_join_holder_matches') or 0) != (base.get('token_count') or 0):
        guidance.append('SOME_TOKENS_LACK_HOLDER: some token rows did not match holder rows in base — backfill required')
    if out['delta_bytes'] and out['delta_bytes'] > 1024 * 1024 * 5:
        guidance.append('MEASURABLE_SAVING: trial shows >5MB disk reduction after dropping legacy token.creator_address')
    elif out['delta_bytes'] and out['delta_bytes'] > 0:
        guidance.append('SMALL_SAVING: trial shows small reduction (consider index/page effects)')
    else:
        guidance.append('NO_SAVING: no observable disk reduction — interning may not help further for this dataset')
    out['guidance'] = guidance
    return out


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(description='Run an address-interning trial (safe by default)')
    p.add_argument('--src', required=True, help='Source SQLite DB')
    p.add_argument('--work-dir', default=f'/tmp/teia_intern_trial_{now_ts()}', help='Directory to store copies and report')
    p.add_argument('--top', type=int, default=20, help='Top-N creators to display')
    p.add_argument('--vacuum', action='store_true', help='VACUUM copies before measuring')
    p.add_argument('--inplace', action='store_true', help='Run trial in-place on the source DB (DANGEROUS)')
    p.add_argument('--yes-ireally-mean-it', action='store_true', help='Required to enable --inplace')
    p.add_argument('--address', help='Force a specific address for micro-benchmarks')
    args = p.parse_args(list(argv) if argv else None)

    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        print('Source DB not found:', src)
        return 2

    workdir = Path(args.work_dir).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    baseline_copy = workdir / (src.stem + '.baseline.sqlite3')
    trial_copy = workdir / (src.stem + '.trial.sqlite3')

    print('Working directory:', workdir)
    print('Creating baseline copy...')
    shutil.copy2(src, baseline_copy)

    print('Creating trial copy...')
    shutil.copy2(src, trial_copy)

    if args.vacuum:
        print('VACUUMing baseline copy...')
        vacuum_inplace(baseline_copy)

    print('Benchmarking baseline (pre-trial)...')
    base_report = bench_db(baseline_copy, vacuum=False, address=args.address)

    print('Performing token.creator_address DROP trial on trial copy...')
    perform_token_drop_trial(src_path=baseline_copy, dst_path=trial_copy)

    if args.vacuum:
        print('VACUUMing trial copy (post-trial)...')
        vacuum_inplace(trial_copy)

    print('Benchmarking trial (post-trial)...')
    trial_report = bench_db(trial_copy, vacuum=False, address=args.address)

    interp = interpret_results(base_report, trial_report)

    out = {
        'generated_at': now_ts(),
        'source': str(src),
        'workdir': str(workdir),
        'baseline_copy': str(baseline_copy),
        'trial_copy': str(trial_copy),
        'base_report': base_report,
        'trial_report': trial_report,
        'interpretation': interp,
    }

    out_path = workdir / f'interning_trial_report-{now_ts()}.json'
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding='utf-8')

    # Human summary
    print('\n' + '=' * 72)
    print('Interning trial summary:')
    print(f" baseline file: {baseline_copy}  ({db_file_size(baseline_copy)//1024**2} MiB)")
    print(f" trial file:    {trial_copy}  ({db_file_size(trial_copy)//1024**2} MiB)")
    delta = interp.get('delta_bytes') or 0
    print(f" delta (bytes): {delta}  (~{delta/1024**2:.2f} MiB)\n")
    print('Quick guidance:')
    for g in interp.get('guidance', []):
        print(' -', g)
    print('\nFull JSON report written to:', out_path)

    print('\nNext recommended action:')
    if 'MEASURABLE_SAVING' in ' '.join(interp.get('guidance', [])):
        print(' - Schedule a follow-up migration to DROP legacy `creator_address` from `token` in a controlled rollout (backups + monitoring).')
    else:
        print(' - Do NOT drop columns yet; run cold reindex comparisons or evaluate other high-volume columns (swap/trade) for interning.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
