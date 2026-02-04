import os
import asyncpg
from contextlib import asynccontextmanager

# Production environment would use env vars
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/teia_ecosystem")

@asynccontextmanager
async def get_db_conn():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()

async def fetch_rows(query, *args):
    async with get_db_conn() as conn:
        return await conn.fetch(query, *args)

async def fetch_row(query, *args):
    async with get_db_conn() as conn:
        return await conn.fetchrow(query, *args)
