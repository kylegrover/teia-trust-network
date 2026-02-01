# database.py
from sqlite_utils import Database

def get_db():
    return Database("trust_network.db")

def init_db():
    db = get_db()
    
    # 1. The Trust Graph
    if "edges" not in db.table_names():
        db["edges"].create({
            "source": str,
            "target": str,
            "token_id": str,
            "contract": str,
            "timestamp": str,
        }, pk=("source", "target", "token_id"))
        db["edges"].create_index(["source", "target"])

    # 2. Indexer State (The Bookmark)
    if "state" not in db.table_names():
        db["state"].create({
            "key": str,
            "value": int, 
        }, pk="key")
        
    print("✅ Database initialized.")

if __name__ == "__main__":
    init_db()