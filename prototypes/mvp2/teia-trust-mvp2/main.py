from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import get_index_conn, get_app_conn
from typing import Optional, List
from pydantic import BaseModel
from engine import TrustEngine
import asyncio

app = FastAPI(title="Teia Trust API MVP2 (Multi-DB)")

# Global engine instance
engine = TrustEngine()

@app.on_event("startup")
async def startup_event():
    # Pre-load the graph into memory for fast PPR calculations
    # In a prod environment, we'd do this in a background task
    asyncio.create_task(engine.load_graph())

class Profile(BaseModel):
    address: str
    id: int
    alias: Optional[str]
    logo: Optional[str]
    score: float
    rank: Optional[int]
    role: Optional[str] = "collector"
    tags: List[str] = []
    subjective_score: float = 0.0

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
    role: Optional[str] = "collector"

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
    # 1. Fetch metadata from INDEX DB - Keep it simple, just holder table
    async with get_index_conn() as conn:
        if isinstance(address_or_id, str) and address_or_id.startswith('tz'):
            h_row = await conn.fetchrow("""
                SELECT h.id, h.address, h.name, 
                       (SELECT COUNT(*) FROM token t WHERE t.creator_id = h.id LIMIT 1) > 0 as is_artist,
                       (SELECT SUM(trade_count) FROM trust_connections tc WHERE tc.source_id = h.id) as total_buys,
                       h.first_seen < '2021-06-01'::timestamp as is_og
                FROM holder h
                WHERE h.address = $1
            """, address_or_id)
        else:
            h_row = await conn.fetchrow("""
                SELECT h.id, h.address, h.name,
                       (SELECT COUNT(*) FROM token t WHERE t.creator_id = h.id LIMIT 1) > 0 as is_artist,
                       (SELECT SUM(trade_count) FROM trust_connections tc WHERE tc.source_id = h.id) as total_buys,
                       h.first_seen < '2021-06-01'::timestamp as is_og
                FROM holder h
                WHERE h.id = $1
            """, int(address_or_id))
    
    if not h_row:
        raise HTTPException(status_code=404, detail="Holder not found")
    
    role = "collector"
    if h_row['is_artist']: role = "artist"
    if (h_row['total_buys'] or 0) > 500: role = "whale"
    if h_row['is_og']: role = "og" 
    if h_row['is_artist'] and h_row['is_og']: role = "og_artist"

    # 2. Fetch scores from APP DB
    async with get_app_conn() as conn:
        s_row = await conn.fetchrow("""
            SELECT score, rank FROM trust_scores WHERE holder_id = $1
        """, h_row['id'])

    # 3. Fetch top tags if artist
    tags = []
    if h_row['is_artist']:
        async with get_index_conn() as conn:
            tag_rows = await conn.fetch("""
                SELECT tag FROM artist_tags_summary 
                WHERE creator_id = $1 
                ORDER BY usage_count DESC 
                LIMIT 5
            """, h_row['id'])
            tags = [r['tag'] for r in tag_rows]

    return Profile(
        address=h_row['address'],
        id=h_row['id'],
        alias=h_row['name'],
        logo=None, 
        score=s_row['score'] if s_row else 0.0,
        rank=s_row['rank'] if s_row else None,
        role=role,
        tags=tags
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
    
    # Compute Subjective Scores (Personalized PageRank)
    # This identifies "who matters to YOU" specifically
    ppr = engine.compute_personalized_pagerank(center.id)
    max_ppr = max(ppr.values()) if ppr else 0.00001
    
    async with get_index_conn() as idx_conn:
        # 1. First Degree - People center directly supports
        first_degree_rows = await idx_conn.fetch("""
            SELECT target_id, trade_count 
            FROM trust_connections 
            WHERE source_id = $1 
            ORDER BY trade_count DESC 
            LIMIT 80
        """, center.id)
        
        first_degree_ids = [r['target_id'] for r in first_degree_rows]
        
        # 2. Second Degree - Social Discovery
        second_degree_rows = await idx_conn.fetch("""
            SELECT target_id, source_id, trade_count 
            FROM (
                SELECT target_id, source_id, trade_count,
                       ROW_NUMBER() OVER(PARTITION BY source_id ORDER BY trade_count DESC) as rank
                FROM trust_connections
                WHERE source_id = ANY($1)
                  AND target_id != $2
                  AND target_id != ANY($1)
            ) as sub
            WHERE rank <= 3 -- Slightly higher discovery limit for PPR
            LIMIT 150
        """, first_degree_ids, center.id)
        
        all_target_ids = list(set(first_degree_ids + [r['target_id'] for r in second_degree_rows] + [center.id]))
        
        # 3. Resolve metadata and roles
        nodes_metadata = await idx_conn.fetch("""
            SELECT h.id, h.address, h.name,
                   (SELECT COUNT(*) FROM token t WHERE t.creator_id = h.id LIMIT 1) > 0 as is_artist,
                   (SELECT SUM(trade_count) FROM trust_connections tc WHERE tc.source_id = h.id) as total_buys,
                   h.first_seen < '2021-06-01'::timestamp as is_og
            FROM holder h
            WHERE h.id = ANY($1)
        """, all_target_ids)

        # 4. Fetch Tags for Artists in view
        artist_tags_map = {}
        tag_rows = await idx_conn.fetch("""
            SELECT creator_id, array_agg(tag) as tags
            FROM (
                SELECT creator_id, tag 
                FROM artist_tags_summary 
                WHERE creator_id = ANY($1)
                ORDER BY usage_count DESC
            ) as t
            GROUP BY creator_id
        """, [r['id'] for r in nodes_metadata if r['is_artist']])
        for r in tag_rows:
            artist_tags_map[r['creator_id']] = r['tags'][:3] # Top 3 tags
    
    # 5. Resolve global scores (from app db)
    async with get_app_conn() as app_conn:
        scores_rows = await app_conn.fetch("""
            SELECT holder_id, score, rank FROM trust_scores WHERE holder_id = ANY($1)
        """, all_target_ids)
        score_map = {r['holder_id']: (r['score'], r['rank']) for r in scores_rows}

    # Helper to calculate role and Traffic Light status
    def get_role(row):
        if row['is_artist'] and row['is_og']: return "og_artist"
        if row['is_artist']: return "artist"
        if (row['total_buys'] or 0) > 500: return "whale"
        if row['is_og']: return "og"
        return "collector"

    def get_status(nid, global_score, subjective_score):
        if nid == center.id: return "CENTER"
        if nid in first_degree_ids: return "GREEN" # Directly Trusted
        if subjective_score > 0.1: return "GREEN" # High Personalized trust
        if global_score > 5.0: return "YELLOW" # Popular but not directly connected
        return "GRAY" # Unknown / Low Signal

    # 6. Build Final Node List
    nodes = []
    for n in nodes_metadata:
        role = get_role(n)
        s, r = score_map.get(n['id'], (0.0, None))
        sub_s = (ppr.get(n['id'], 0) / max_ppr) * 100
        
        nodes.append({
            "id": n['id'],
            "label": n['name'] or n['address'][:6],
            "title": n['address'],
            "name": n['name'],
            "address": n['address'],
            "score": s,
            "rank": r,
            "role": role,
            "tags": artist_tags_map.get(n['id'], []),
            "subjective_score": sub_s,
            "status": get_status(n['id'], s, sub_s),
            "group": "center" if n['id'] == center.id else ("1st" if n['id'] in first_degree_ids else "2nd")
        })

    # 7. Build Simplified Edges
    async with get_index_conn() as idx_conn:
        discovery_ids = [r['target_id'] for r in second_degree_rows]
        all_edges = await idx_conn.fetch("""
            SELECT source_id, target_id, trade_count 
            FROM trust_connections 
            WHERE source_id = ANY($1) AND target_id = ANY($1)
              AND (
                (source_id = $2 OR target_id = $2)
                OR (source_id = ANY($3) AND target_id = ANY($3))
                OR (target_id = ANY($4))
              )
              AND trade_count > 0
        """, all_target_ids, center.id, first_degree_ids, discovery_ids)

    return {
        "nodes": nodes,
        "edges": [
            {
                "from": e['source_id'], 
                "to": e['target_id'], 
                "value": e['trade_count']
            } for e in all_edges
        ]
    }
