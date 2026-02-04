from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import fetch_row, fetch_rows
from typing import Optional, List
from pydantic import BaseModel

app = FastAPI(title="Teia Trust API MVP2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Profile(BaseModel):
    address: str
    id: int
    alias: Optional[str]
    logo: Optional[str]
    score: float
    rank: Optional[int]

class TrustResponse(BaseModel):
    observer: Profile
    target: Profile
    direct_connection: bool
    strength: int
    status: str
    reason: str

async def get_profile(address_or_id: str | int) -> Profile:
    if isinstance(address_or_id, str) and address_or_id.startswith('tz'):
        # Resolve by address
        row = await fetch_row("""
            SELECT h.id, h.address, m.alias, m.logo, s.score, s.rank
            FROM holder h
            LEFT JOIN holder_metadata m ON h.id = m.holder_id
            LEFT JOIN trust_scores s ON h.id = s.holder_id
            WHERE h.address = $1
        """, address_or_id)
    else:
        # Resolve by ID
        row = await fetch_row("""
            SELECT h.id, h.address, m.alias, m.logo, s.score, s.rank
            FROM holder h
            LEFT JOIN holder_metadata m ON h.id = m.holder_id
            LEFT JOIN trust_scores s ON h.id = s.holder_id
            WHERE h.id = $1
        """, int(address_or_id))
    
    if not row:
        raise HTTPException(status_code=404, detail="Holder not found")
    
    return Profile(
        address=row['address'],
        id=row['id'],
        alias=row['alias'],
        logo=row['logo'],
        score=row['score'] or 0.0,
        rank=row['rank']
    )

@app.get("/trust/{observer_address}/{target_address}", response_model=TrustResponse)
async def get_trust(observer_address: str, target_address: str):
    obs = await get_profile(observer_address)
    tgt = await get_profile(target_address)
    
    # 1. Did Observer buy from Target? (Direct Trust)
    conn_at_b = await fetch_row("""
        SELECT trade_count 
        FROM trust_connections 
        WHERE source_id = $1 AND target_id = $2
    """, obs.id, tgt.id)
    
    # 2. Did Target buy from Observer? (Reciprocity)
    conn_bt_a = await fetch_row("""
        SELECT trade_count 
        FROM trust_connections 
        WHERE source_id = $1 AND target_id = $2
    """, tgt.id, obs.id)
    
    strength_a = conn_at_b['trade_count'] if conn_at_b else 0
    strength_b = conn_bt_a['trade_count'] if conn_bt_a else 0
    
    status = "YELLOW"
    reason = "No direct historical connection."
    
    if strength_a > 0 and strength_b > 0:
        status = "BLUE"
        # Since strength_a and strength_b are separate buy counts, we show both
        reason = f"Mutual Trust: A bought {strength_a} items, B bought {strength_b} items."
    elif strength_a > 0:
        status = "GREEN"
        reason = f"Direct Support: Collector has bought {strength_a} items from artist."

    return {
        "observer": obs,
        "target": tgt,
        "direct_connection": strength_a > 0,
        "strength": strength_a,
        "status": status,
        "reason": reason
    }

@app.get("/graph/{address}")
async def get_graph(address: str):
    center = await get_profile(address)
    
    # Fetch 1st and 2nd degree connections from trust_connections
    # 1. Direct connections from center
    first_degree = await fetch_rows("""
        SELECT target_id, trade_count 
        FROM trust_connections 
        WHERE source_id = $1 
        ORDER BY trade_count DESC 
        LIMIT 50
    """, center.id)
    
    target_ids = [r['target_id'] for r in first_degree]
    target_ids.append(center.id)
    
    # 2. Get edges between these people to show the "Network density"
    edges = await fetch_rows("""
        SELECT source_id, target_id, trade_count 
        FROM trust_connections 
        WHERE source_id = ANY($1) AND target_id = ANY($1)
    """, target_ids)
    
    # 3. Resolve names for all nodes
    nodes = await fetch_rows("""
        SELECT h.id, h.address, m.alias, m.logo, s.score
        FROM holder h
        LEFT JOIN holder_metadata m ON h.id = m.holder_id
        LEFT JOIN trust_scores s ON h.id = s.holder_id
        WHERE h.id = ANY($1)
    """, target_ids)
    
    return {
        "nodes": [
            {
                "id": n['id'], 
                "label": n['alias'] or n['address'][:6], 
                "title": n['address'],
                "value": n['score'] or 1.0,
                "group": "center" if n['id'] == center.id else "collector"
            } for n in nodes
        ],
        "edges": [
            {
                "from": e['source_id'], 
                "to": e['target_id'], 
                "value": e['trade_count'],
                "arrows": "to"
            } for e in edges
        ]
    }
