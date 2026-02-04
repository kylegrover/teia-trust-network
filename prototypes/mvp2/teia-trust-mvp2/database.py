import os
import asyncpg
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Connections for the two isolated databases
INDEX_DB_URL = os.getenv("INDEX_DB_URL")
APP_DB_URL = os.getenv("APP_DB_URL")

@asynccontextmanager
async def get_index_conn():
    """Connection to the Read-Only Indexer DB"""
    conn = await asyncpg.connect(INDEX_DB_URL)
    try:
        yield conn
    finally:
        await conn.close()

@asynccontextmanager
async def get_app_conn():
    """Connection to the Read-Write MVP DB"""
    conn = await asyncpg.connect(APP_DB_URL)
    try:
        yield conn
    finally:
        await conn.close()
