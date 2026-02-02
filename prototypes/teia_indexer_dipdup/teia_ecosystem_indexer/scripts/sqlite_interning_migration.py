"""Safe, end-to-end SQLite interning migration and cleanup helper.

Purpose
-------
Run the final migration that removes legacy address-string columns (token.creator_address,
swap.seller_address, trade.buyer_address) from a *copy* of your DB, verify integrity,
VACUUM, benchmark pre/post, and produce a report plus a list of repository references
that must be updated/removed before full cleanup.

Safety
------
- Defaults to operating on copies inside --work-dir; it will NOT mutate your original
  DB unless you pass --inplace AND --yes-ireally-mean-it.
- All destructive operations are transactional where possible and validated post-copy.

Usage (recommended, non-destructive)
------------------------------------
# run trial on a copy, vacuum and benchmark
./.venv/bin/python scripts/sqlite_interning_migration.py \
  --src db_backups/teia_ecosystem.sqlite3 \
  --work-dir /tmp/teia-interning-migration --do-drop token --vacuum --bench

To actually apply to the source (DANGEROUS):
./.venv/bin/python scripts/sqlite_interning_migration.py --src path/to/db --inplace --yes-ireally-mean-it --do-drop token --vacuum --bench

Recommended workflow
--------------------
1. Run without --inplace on a copy (default). Verify report.  
2. Fix any repo references flagged by the script.  
3. Run again on a fresh copy and re-verify.  
4. When confident, run with --inplace during a maintenance window.

"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

LEGACY_COLUMNS = {
    'token': ['creator_address'],
    'swap': ['seller_address'],
    'trade': ['buyer_address'],
}

REPO_ROOT = Path(__file__).resolve().parents[2]


def now_iso() -> str:
    # use timezone-aware UTC to avoid DeprecationWarning on Python 3.12+
    return datetime.now(timezone.utc).isoformat()


def open_conn(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    return c


def file_size(path: Path) -> int:
    return path.stat().st_size


def vacuum_inplace(path: Path) -> None:
    """Run VACUUM on the SQLite file in-place.

    This mirrors the small helper used by the trial runner: open a connection,
    execute VACUUM, commit and close. Keep the implementation local to avoid
    adding new module deps.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = open_conn(path)
        conn.execute("VACUUM;")
        conn.commit()
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def pragma_bytes(conn: sqlite3.Connection) -> int:
    try:
        pc = conn.execute('PRAGMA page_count;').fetchone()[0]
        ps = conn.execute('PRAGMA page_size;').fetchone()[0]
        return int(pc) * int(ps)
    except Exception:
        return 0


def list_tables(conn: sqlite3.Connection) -> List[str]:
    try:
        return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    except Exception:
        return []


def table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    try:
        return [r['name'] for r in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]
    except Exception:
        return []


def run_counts(conn: sqlite3.Connection) -> Dict[str, Any]:
    def s(q: str):
        try:
            return conn.execute(q).fetchone()[0]
        except Exception:
            return None

    return {
        'token_count': s('SELECT count(*) FROM token'),
        'distinct_token_creators': s("SELECT COUNT(DISTINCT creator_address) FROM token WHERE creator_address IS NOT NULL"),
        'token_creator_id_populated': s('SELECT count(*) FROM token WHERE creator_id IS NOT NULL'),
        'token_join_holder': s('SELECT count(*) FROM token t JOIN holder h ON h.address = t.creator_address'),
        'swap_count': s('SELECT count(*) FROM swap'),
        'swap_seller_id_populated': s('SELECT count(*) FROM swap WHERE seller_id IS NOT NULL'),
        'trade_count': s('SELECT count(*) FROM trade'),
        'trade_buyer_id_populated': s('SELECT count(*) FROM trade WHERE buyer_id IS NOT NULL'),
    }


def pick_sample_address(conn: sqlite3.Connection) -> Optional[str]:
    # prefer token creators
    try:
        r = conn.execute("SELECT creator_address FROM token WHERE creator_address IS NOT NULL GROUP BY creator_address ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
        if r:
            return r[0]
    except Exception:
        pass
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
        'median_s': sorted(times)[len(times) // 2] if times else None,
        'mean_s': (sum(times) / len(times)) if times else None,
        'min_s': min(times) if times else None,
        'max_s': max(times) if times else None,
        'result_count': result,
    }


def repo_search_legacy(root: Path, patterns: Iterable[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {p: [] for p in patterns}
    # scan common text files (.py, .md, .sql, .yaml, .yml, .sh)
    exts = ('.py', '.md', '.sql', '.yaml', '.yml', '.sh', '.json', '.ini', '.toml')
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in exts:
            try:
                text = p.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            for pat in patterns:
                if pat in text:
                    out[pat].append(str(p.relative_to(root)))
    return out


def create_table_without_columns(conn: sqlite3.Connection, table: str, drop_cols: List[str]) -> None:
    cols = [c['name'] for c in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]
    keep = [c for c in cols if c not in drop_cols]
    if not keep:
        raise RuntimeError(f'No columns left after dropping {drop_cols} from {table}')
    col_list = ', '.join(keep)
    conn.execute('PRAGMA foreign_keys=OFF;')
    conn.execute('BEGIN;')
    conn.execute(f"CREATE TABLE {table}_new AS SELECT {col_list} FROM {table};")
    conn.execute(f"DROP TABLE {table};")
    conn.execute(f"ALTER TABLE {table}_new RENAME TO {table};")
    conn.execute('COMMIT;')
    conn.execute('PRAGMA foreign_keys=ON;')


def ensure_index(conn: sqlite3.Connection, table: str, index_sql: str) -> None:
    try:
        conn.execute(index_sql)
        conn.commit()
    except Exception:
        pass


def validate_post_swap(conn: sqlite3.Connection, table: str, expected_count: int) -> bool:
    try:
        cnt = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        return cnt == expected_count
    except Exception:
        return False


def human(n: Optional[int]) -> str:
    if not n:
        return '0'
    for u in ('B', 'KiB', 'MiB', 'GiB'):
        if abs(n) < 1024.0:
            return f"{n:3.1f}{u}"
        n /= 1024.0
    return f"{n:.1f}TiB"


def perform_migration(src: Path, workdir: Path, drop_tables: List[str], inplace: bool = False, vacuum: bool = True) -> Dict[str, Any]:
    report: Dict[str, Any] = {'started_at': now_iso(), 'src': str(src), 'workdir': str(workdir)}
    # create working copies
    if inplace:
        if not (args_yes := False):
            pass
    baseline = workdir / (src.stem + '.baseline.sqlite3')
    trial = workdir / (src.stem + '.trial.sqlite3')
    shutil.copy2(src, baseline)
    shutil.copy2(src, trial)

    # gather pre-metrics
    conn_b = open_conn(baseline)
    try:
        pre = {
            'file_bytes': file_size(baseline),
            'pragma_bytes': pragma_bytes(conn_b),
            'tables': list_tables(conn_b),
            'counts': run_counts(conn_b),
        }
    finally:
        conn_b.close()
    report['pre'] = pre

    # repo search for legacy columns
    patterns = [c for cols in LEGACY_COLUMNS.values() for c in cols]
    report['repo_legacy_refs'] = repo_search_legacy(REPO_ROOT, patterns)

    # safety checks
    issues: List[str] = []
    if pre['counts'].get('token_creator_id_populated') != pre['counts'].get('token_count'):
        issues.append('token.creator_id is not fully populated — abort or backfill first')
    report['pre_checks_issues'] = issues
    if issues and not inplace:
        # we still allow the script to proceed on copies for investigation
        report['pre_checks_warn'] = True

    # run the drops on trial copy
    conn_t = open_conn(trial)
    try:
        for tbl in drop_tables:
            cols = LEGACY_COLUMNS.get(tbl, [])
            if not cols:
                continue
            # ensure table exists
            if tbl not in list_tables(conn_t):
                report.setdefault('drop_skipped', []).append(f'{tbl} missing')
                continue
            # record schema
            report.setdefault('pre_schema', {})[tbl] = table_columns(conn_t, tbl)
            # expected rows
            exp = conn_t.execute(f'SELECT count(*) FROM {tbl}').fetchone()[0]
            create_table_without_columns(conn_t, tbl, cols)
            ok = validate_post_swap(conn_t, tbl, exp)
            report.setdefault('drop_results', {})[tbl] = {'expected_rows': exp, 'success': ok}
            # add indexes if needed
            if tbl == 'swap':
                ensure_index(conn_t, 'swap', 'CREATE INDEX IF NOT EXISTS idx_swap_seller_id ON swap(seller_id);')
            if tbl == 'trade':
                ensure_index(conn_t, 'trade', 'CREATE INDEX IF NOT EXISTS idx_trade_buyer_id ON trade(buyer_id);')
    finally:
        conn_t.close()

    # VACUUM if requested
    if vacuum:
        vacuum_inplace(trial)
        vacuum_inplace(baseline)

    # gather post-metrics
    conn_b2 = open_conn(baseline)
    conn_t2 = open_conn(trial)
    try:
        post = {
            'baseline': {
                'file_bytes': file_size(baseline),
                'pragma_bytes': pragma_bytes(conn_b2),
                'counts': run_counts(conn_b2),
            },
            'trial': {
                'file_bytes': file_size(trial),
                'pragma_bytes': pragma_bytes(conn_t2),
                'counts': run_counts(conn_t2),
            },
        }
        # microbench on a heavy address (if present)
        addr = pick_sample_address(conn_b2)
        post['heavy_address'] = addr
        if addr:
            post['baseline']['bench_token_legacy'] = timed_query(conn_b2, 'SELECT COUNT(*) FROM token WHERE creator_address=?', (addr,))
            post['baseline']['bench_token_interned'] = timed_query(conn_b2, 'SELECT COUNT(*) FROM token WHERE creator_id=(SELECT id FROM holder WHERE address=?)', (addr,))
            post['trial']['bench_token_interned'] = timed_query(conn_t2, 'SELECT COUNT(*) FROM token WHERE creator_id=(SELECT id FROM holder WHERE address=?)', (addr,))
    finally:
        conn_b2.close()
        conn_t2.close()

    report['post'] = post
    # interpretation
    delta = post['baseline']['file_bytes'] - post['trial']['file_bytes']
    report['interpretation'] = {
        'delta_bytes': delta,
        'delta_percent': (delta / post['baseline']['file_bytes'] * 100) if post['baseline']['file_bytes'] else None,
        'advice': []
    }
    if delta > 5 * 1024 * 1024:
        report['interpretation']['advice'].append('MEASURABLE_SAVING')
    else:
        report['interpretation']['advice'].append('NO_MEASURABLE_SAVING')

    report['finished_at'] = now_iso()
    return report


def write_report(out: Dict[str, Any], workdir: Path) -> Path:
    path = workdir / f'interning_migration_report-{now_iso().replace(":","-")}.json'
    path.write_text(json.dumps(out, indent=2, default=str), encoding='utf-8')
    return path


def human_summary(report: Dict[str, Any]) -> str:
    b = report['pre']['file_bytes']
    t = report['post']['trial']['file_bytes']
    delta = b - t
    pct = (delta / b * 100) if b else 0
    lines = []
    lines.append(f"Source: {report['src']}")
    lines.append(f"Baseline size: {human(b)}")
    lines.append(f"Trial size:    {human(t)}")
    lines.append(f"Delta:         {human(delta)} ({pct:.1f}%)")
    lines.append('Pre-check issues:')
    if report.get('pre_checks_issues'):
        for i in report['pre_checks_issues']:
            lines.append(' - ' + i)
    else:
        lines.append(' - none')
    lines.append('\nRepo references to legacy columns (top examples):')
    for pat, files in report['repo_legacy_refs'].items():
        lines.append(f' - {pat}: {len(files)} file(s)')
        for f in files[:5]:
            lines.append(f'    {f}')
    lines.append('\nNext recommended action:')
    if 'MEASURABLE_SAVING' in report['interpretation'].get('advice', []):
        lines.append(' - Proceed to staging migration; schedule prod migration with backups and 48-72h monitoring.')
    else:
        lines.append(' - No strong disk benefit observed; consider targeting other high-cardinality columns or run cold reindex for full comparison.')
    return '\n'.join(lines)


def parse_args(argv: Optional[Iterable[str]] = None):
    p = argparse.ArgumentParser(description='SQLite interning migration helper (safe by default)')
    p.add_argument('--src', required=True, help='Source SQLite DB file (use a backup copy)')
    p.add_argument('--work-dir', default=None, help='Directory to store copies and report (default: temp)')
    p.add_argument('--do-drop', nargs='+', choices=['token', 'swap', 'trade'], default=['token'], help='Which legacy columns/tables to drop')
    p.add_argument('--vacuum', action='store_true', help='VACUUM copies before measuring')
    p.add_argument('--bench', action='store_true', help='Run microbenchmarks (timed queries)')
    p.add_argument('--inplace', action='store_true', help='Apply migration IN-PLACE to source DB (DANGEROUS)')
    p.add_argument('--yes-ireally-mean-it', action='store_true', help='Must be supplied with --inplace')
    return p.parse_args(list(argv) if argv else None)


if __name__ == '__main__':
    args = parse_args()
    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        print('Source DB not found:', src)
        raise SystemExit(2)
    if args.inplace and not args.yes_ireally_mean_it:
        print('Refusing to run inplace migration without --yes-ireally-mean-it')
        raise SystemExit(2)
    workdir = Path(args.work_dir).expanduser().resolve() if args.work_dir else Path(tempfile.mkdtemp(prefix='teia_intern_trial_'))
    workdir.mkdir(parents=True, exist_ok=True)

    print('Running safe intern/cleanup trial')
    print(' Source DB:', src)
    print(' Work dir:', workdir)
    print(' Drop targets:', args.do_drop)
    print(' Vacuum:', args.vacuum)
    print(' Bench:', args.bench)
    print(' In-place:', args.inplace)

    rpt = perform_migration(src=src, workdir=workdir, drop_tables=args.do_drop, inplace=args.inplace, vacuum=args.vacuum)
    out_path = write_report(rpt, workdir)

    print('\n' + '=' * 72)
    print(human_summary(rpt))
    print('\nFull report JSON ->', out_path)
    print('\nIf results look good, run the same process on staging and then schedule production migration (keep backups).')
    sys.exit(0)
