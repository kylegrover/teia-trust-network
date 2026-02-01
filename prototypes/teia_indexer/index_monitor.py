import sqlite3
import time

while True:
    conn = sqlite3.connect("teia_index.db")
    c = conn.cursor()
    
    # Get Counts
    tokens = c.execute("SELECT count(*) FROM tokens").fetchone()[0]
    holders = c.execute("SELECT count(*) FROM holders").fetchone()[0]
    events = c.execute("SELECT count(*) FROM events").fetchone()[0]
    
    # Get Progress Cursors
    try:
        token_cursor = c.execute("SELECT value FROM state WHERE key='token_offset'").fetchone()[0]
        event_cursor = c.execute("SELECT value FROM state WHERE key='last_op_id'").fetchone()[0]
    except:
        token_cursor, event_cursor = 0, 0

    print(f"\r📊 Status: {tokens:,} Tokens | {holders:,} Owners | {events:,} Sales/Listings | Cursor: {event_cursor}", end="")
    conn.close()
    time.sleep(5)