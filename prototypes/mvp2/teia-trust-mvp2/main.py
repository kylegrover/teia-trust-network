from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import get_index_conn, get_app_conn
from typing import Optional, List
from pydantic import BaseModel

app = FastAPI(title="Teia Trust API MVP2 (Multi-DB)")

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

def format_logo_url(logo: Optional[str]) -> Optional[str]:
    if not logo:
        # Fallback to identicon service if no logo exists
        return None
    if logo.startswith('ipfs://'):
        return logo.replace('ipfs://', 'https://cloudflare-ipfs.com/ipfs/')
    return logo

class TrustResponse(BaseModel):
    observer: Profile
    target: Profile
    direct_connection: bool
    strength: int
    status: str
    reason: str

async def get_profile(address_or_id: str | int) -> Profile:
    # 1. Fetch metadata from INDEX DB
    async with get_index_conn() as conn:
        if isinstance(address_or_id, str) and address_or_id.startswith('tz'):
            h_row = await conn.fetchrow("""
                SELECT h.id, h.address, 
                       COALESCE(h.name, m.alias, m.content->>'name', m.content->>'alias') as alias, 
                       COALESCE(m.logo, m.content->>'logo', m.content->>'identicon') as logo
                FROM holder h
                LEFT JOIN holder_metadata m ON h.id = m.holder_id
                WHERE h.address = $1
            """, address_or_id)
        else:
            h_row = await conn.fetchrow("""
                SELECT h.id, h.address, 
                       COALESCE(h.name, m.alias, m.content->>'name', m.content->>'alias') as alias, 
                       COALESCE(m.logo, m.content->>'logo', m.content->>'identicon') as logo
                FROM holder h
                LEFT JOIN holder_metadata m ON h.id = m.holder_id
                WHERE h.id = $1
            """, int(address_or_id))
    
    if not h_row:
        raise HTTPException(status_code=404, detail="Holder not found")
    
    # 2. Fetch scores from APP DB
    async with get_app_conn() as conn:
        s_row = await conn.fetchrow("""
            SELECT score, rank FROM trust_scores WHERE holder_id = $1
        """, h_row['id'])

    return Profile(
        address=h_row['address'],
        id=h_row['id'],
        alias=h_row['alias'],
        logo=format_logo_url(h_row['logo']),
        score=s_row['score'] if s_row else 0.0,
        rank=s_row['rank'] if s_row else None
    )

@app.get("/trust/{observer_address}/{target_address}", response_model=TrustResponse)
async def get_trust(observer_address: str, target_address: str):
    obs = await get_profile(observer_address)
    tgt = await get_profile(target_address)
    
    # Check for direct and mutual trust in the READ-ONLY index view
    async with get_index_conn() as conn:
        # 1. Did Observer buy from Target? (Direct Trust)
        conn_at_b = await conn.fetchrow("""
            SELECT trade_count 
            FROM trust_connections 
            WHERE source_id = $1 AND target_id = $2
        """, obs.id, tgt.id)
        
        # 2. Did Target buy from Observer? (Reciprocity)
        conn_bt_a = await conn.fetchrow("""
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
    
    async with get_index_conn() as idx_conn:
        # 1. Direct connections from center (from index)
        first_degree = await idx_conn.fetch("""
            SELECT target_id, trade_count 
            FROM trust_connections 
            WHERE source_id = $1 
            ORDER BY trade_count DESC 
            LIMIT 50
        """, center.id)
        
        target_ids = [r['target_id'] for r in first_degree]
        target_ids.append(center.id)
        
        # 2. Get edges between these people (from index)
        edges_rows = await idx_conn.fetch("""
            SELECT source_id, target_id, trade_count 
            FROM trust_connections 
            WHERE source_id = ANY($1) AND target_id = ANY($1)
        """, target_ids)
        
        # 3. Resolve metadata (from index)
        nodes_metadata = await idx_conn.fetch("""
            SELECT h.id, h.address, 
                   COALESCE(h.name, m.alias, m.content->>'name', m.content->>'alias') as alias, 
                   COALESCE(m.logo, m.content->>'logo', m.content->>'identicon') as logo
            FROM holder h
            LEFT JOIN holder_metadata m ON h.id = m.holder_id
            WHERE h.id = ANY($1)
        """, target_ids)
    
    # 4. Resolve scores (from app db)
    async with get_app_conn() as app_conn:
        scores_rows = await app_conn.fetch("""
            SELECT holder_id, score FROM trust_scores WHERE holder_id = ANY($1)
        """, target_ids)
        score_map = {r['holder_id']: r['score'] for r in scores_rows}
    
    return {
        "nodes": [
            {
                "id": n['id'], 
                "label": n['alias'] or n['address'][:6], 
                "title": n['address'],
                "image": format_logo_url(n['logo']),
                "value": score_map.get(n['id'], 1.0),
                "group": "center" if n['id'] == center.id else "collector"
            } for n in nodes_metadata
        ],
        "edges": [
            {
                "from": e['source_id'], 
                "to": e['target_id'], 
                "value": e['trade_count'],
                "arrows": "to"
            } for e in edges_rows
        ]
    }
