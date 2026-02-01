# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlite_utils import Database
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Teia Trust MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    return Database("trust_network.db")

class TrustSignal(BaseModel):
    observer: str
    target: str
    status: str
    reason: str
    connection_strength: int
    global_trust_score: float # NEW
    global_rank: Optional[int] # NEW

@app.get("/trust/{observer_address}/{target_address}", response_model=TrustSignal)
def get_trust_score(observer_address: str, target_address: str):
    db = get_db()
    
    # 1. Direct Trust (Local)
    matches = list(db["edges"].rows_where(
        "source = ? AND target = ?", 
        [observer_address, target_address]
    ))
    strength = len(matches)
    
    # 2. Global Trust (Network Reputation)
    score_row = db["scores"].get(target_address)
    global_score = score_row["score"] if score_row else 0.0
    rank = score_row["rank"] if score_row else None

    # Logic: Green if connected directly, Yellow otherwise (for now)
    status = "GREEN" if strength > 0 else "YELLOW"
    reason = f"Direct collects: {strength}" if strength > 0 else "No direct connection"

    return {
        "observer": observer_address,
        "target": target_address,
        "status": status,
        "reason": reason,
        "connection_strength": strength,
        "global_trust_score": round(global_score, 2),
        "global_rank": rank
    }

@app.get("/graph/{center_address}")
def get_graph_data(center_address: str):
    db = get_db()
    
    # Get nodes and edges (Same logic as before)
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
    
    nodes = set()
    edges = []
    nodes.add(center_address)
    
    for r in rows:
        src = r["source"]
        tgt = r["target"]
        nodes.add(src)
        nodes.add(tgt)
        
        edges.append({
            "from": src, "to": tgt, "arrows": "to",
            "color": {"color": "#4ade80" if src == center_address else "#64748b"}
        })
        
    # Get scores for all these nodes to size them properly
    # Using 'IN' clause for efficiency
    placeholders = ",".join(["?"] * len(nodes))
    score_rows = list(db.query(
        f"SELECT address, score FROM scores WHERE address IN ({placeholders})", 
        list(nodes)
    ))
    score_map = {row["address"]: row["score"] for row in score_rows}

    node_list = []
    for n in nodes:
        # Base size 10, add score (0-100) -> Max size 110ish
        score = score_map.get(n, 0)
        size = 10 + (score * 0.5) 
        
        # Center node is always distinct
        color = "#eab308" if n == center_address else "#94a3b8"
        
        node_list.append({
            "id": n, 
            "label": n[:5] + "...", 
            "title": f"Address: {n}\nTrust Score: {round(score, 1)}", # Tooltip
            "color": color,
            "size": size 
        })

    return {"nodes": node_list, "edges": edges}

@app.get("/stats")
def get_stats():
    db = get_db()
    if "edges" not in db.table_names(): return {}
    return {
        "total_edges": db["edges"].count,
        "total_scored_users": db["scores"].count if "scores" in db.table_names() else 0
    }