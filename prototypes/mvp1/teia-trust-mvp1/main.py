# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlite_utils import Database
from pydantic import BaseModel

app = FastAPI(title="Teia Trust MVP")

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    return Database("trust_network.db")

# --- VISUALIZATION ENDPOINT ---
@app.get("/graph/{center_address}")
def get_graph_data(center_address: str):
    db = get_db()
    
    # 1. Fetch "Depth-2" connections
    # (My Direct Connections) + (Their Connections)
    # We limit to 500 edges to prevent browser crash
    sql = """
    WITH my_trusts AS (
        SELECT target FROM edges WHERE source = :center
    )
    SELECT * FROM edges 
    WHERE source = :center 
       OR source IN (SELECT target FROM my_trusts)
       OR target = :center
    LIMIT 500
    """
    
    rows = list(db.query(sql, {"center": center_address}))
    
    # 2. Format for Vis.js
    nodes = set()
    edges = []
    
    # Add the center node (Me)
    nodes.add(center_address)
    
    for r in rows:
        src = r["source"]
        tgt = r["target"]
        
        nodes.add(src)
        nodes.add(tgt)
        
        edges.append({
            "from": src, 
            "to": tgt, 
            "arrows": "to",
            "color": {"color": "#4ade80" if src == center_address else "#64748b"} # Green if direct, Gray if secondary
        })
        
    # Convert sets to list of dicts
    node_list = []
    for n in nodes:
        node_list.append({
            "id": n, 
            "label": n[:5] + "...", # Shorten address for display
            "title": n, # Full address on hover
            "color": "#eab308" if n == center_address else "#94a3b8",
            "size": 25 if n == center_address else 15
        })

    return {"nodes": node_list, "edges": edges}


# --- EXISTING ENDPOINTS ---

class TrustSignal(BaseModel):
    observer: str
    target: str
    status: str
    reason: str
    connection_strength: int

@app.get("/")
def read_root():
    return {"status": "online", "message": "Trust Network Phase 0 is running"}

@app.get("/trust/{observer_address}/{target_address}", response_model=TrustSignal)
def get_trust_score(observer_address: str, target_address: str):
    db = get_db()
    
    # Check direct trust
    matches = list(db["edges"].rows_where(
        "source = ? AND target = ?", 
        [observer_address, target_address]
    ))
    count = len(matches)

    if count > 0:
        return {
            "observer": observer_address,
            "target": target_address,
            "status": "GREEN",
            "reason": f"Directly collected {count} item(s).",
            "connection_strength": count
        }
    
    return {
        "observer": observer_address,
        "target": target_address,
        "status": "YELLOW",
        "reason": "No direct connection found.",
        "connection_strength": 0
    }

@app.get("/stats")
def get_stats():
    db = get_db()
    try:
        if "edges" not in db.table_names():
            return {"total_edges": 0, "sample_edge": None}
        return {
            "total_edges": db["edges"].count,
            "sample_edge": list(db.query("SELECT * FROM edges LIMIT 1"))
        }
    except Exception as e:
        return {"error": str(e)}