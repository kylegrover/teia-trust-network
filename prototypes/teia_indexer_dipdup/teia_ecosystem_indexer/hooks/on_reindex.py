import os
from pathlib import Path

from dipdup.context import HookContext


async def on_reindex(
    ctx: HookContext,
) -> None:
    """Execute only the SQL files that match the active DB dialect.

    DipDup will load all files in `sql/on_reindex/` by default; some projects
    include both `*.sqlite.sql` and `*.postgres.sql`. Running Postgres SQL on
    SQLite fails (and vice-versa). This hook filters files by suffix so the
    appropriate dialect-specific script is executed.
    """
    db_url = os.environ.get('DATABASE_URL', '').lower()
    is_sqlite = db_url.startswith('sqlite') or 'sqlite' in db_url
    is_postgres = db_url.startswith('postgres') or 'postgres' in db_url or 'postgresql' in db_url

    sql_dir = Path(__file__).resolve().parents[1] / 'sql' / 'on_reindex'
    if not sql_dir.exists():
        # fallback to default behaviour (no-op)
        return

    for path in sorted(sql_dir.glob('*.sql')):
        name = path.name.lower()
        # dialect-specific files must end with `.sqlite.sql` or `.postgres.sql`
        if name.endswith('.sqlite.sql') and not is_sqlite:
            continue
        if name.endswith('.postgres.sql') and not is_postgres:
            continue
        # generic .sql files (no dialect suffix) are always executed
        sql = path.read_text(encoding='utf-8')
        await ctx.database.execute_script(sql)
