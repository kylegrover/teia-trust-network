import asyncio
from database import get_index_conn, get_app_conn
import time

from trust_graph import TrustGraph

async def init_score_table():
    async with get_app_conn() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS trust_scores (
                holder_id INTEGER PRIMARY KEY,
                score FLOAT NOT NULL,
                rank INTEGER NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_trust_scores_rank ON trust_scores(rank);
        """)

class TrustEngine:
    """High-level engine that delegates graph work to the rustworkx-backed TrustGraph."""
    def __init__(self):
        # TrustGraph will raise if rustworkx is missing
        self._gsvc = TrustGraph()
        self.global_scores = {}
        self.nodes_loaded = False

    async def load_graph(self):
        print("📥 Loading graph via TrustGraph (rustworkx)...")
        await self._gsvc.load_from_index_db()
        # TrustGraph maps node indices -> DB ids via rev_node_map
        self.nodes_loaded = getattr(self._gsvc, "_nodes_loaded", False)
        if not self.nodes_loaded:
            print("⚠️ No trust connections found.")
            return

        print(f"📊 Graph stats: {len(self._gsvc.node_map)} nodes, {len(list(self._gsvc.graph.weighted_edge_list()))} edges")

    def compute_global_pagerank(self):
        print("🧠 Computing Global PageRank (rustworkx)...")
        # returns mapping node_index -> score
        node_scores = self._gsvc.compute_global_pagerank()
        # map to DB ids
        mapped = {self._gsvc.rev_node_map[n]: s for n, s in node_scores.items()}
        self.global_scores = mapped
        return mapped

    def compute_personalized_pagerank(self, seed_node_id: int):
        # TrustGraph.get_user_trust_vector already returns holder_id -> score
        if not self.nodes_loaded:
            return {}
        return self._gsvc.get_user_trust_vector(seed_node_id)

async def run_trust_algorithm():
    print("🚀 Starting Trust Engine MVP2 (Isolated DB Mode)...")
    start_time = time.time()
    
    await init_score_table()
    
    engine = TrustEngine()
    await engine.load_graph()
    
    if not engine.nodes_loaded:
        return

    scores = engine.compute_global_pagerank()
    
    # 4. Normalize and Rank
    max_score = max(scores.values()) if scores else 1.0
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    # 5. Save to the READ-WRITE App DB
    print(f"💾 Saving {len(sorted_scores)} scores to MVP database...")
    async with get_app_conn() as conn:
        await conn.execute("CREATE TEMP TABLE tmp_scores (holder_id INT, score FLOAT, rank INT)")
        
        batch = [
            (holder_id, (score / max_score) * 100, rank) 
            for rank, (holder_id, score) in enumerate(sorted_scores, 1)
        ]
        
        await conn.copy_records_to_table('tmp_scores', records=batch)
        
        async with conn.transaction():
            await conn.execute("DELETE FROM trust_scores")
            await conn.execute("""
                INSERT INTO trust_scores (holder_id, score, rank)
                SELECT holder_id, score, rank FROM tmp_scores
            """)
            
    end_time = time.time()
    print(f"✅ Trust Engine completed in {end_time - start_time:.2f} seconds.")
            
    end_time = time.time()
    print(f"✅ Trust Engine completed in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    # CLI: rustworkx-only (use uv to manage interpreter & deps)
    import argparse, json

    parser = argparse.ArgumentParser(description="Trust engine CLI (rustworkx)")
    parser.add_argument("--ppr", type=int, help="Compute personalized PageRank for holder_id")
    args = parser.parse_args()

    if args.ppr is not None:
        holder = args.ppr
        async def run_ppr():
            engine = TrustEngine()
            await engine.load_graph()
            vec = engine.compute_personalized_pagerank(holder)
            print(json.dumps({"holder": holder, "ppr_top": sorted(vec.items(), key=lambda x: x[1], reverse=True)[:50]}, default=str))
        asyncio.run(run_ppr())
    else:
        asyncio.run(run_trust_algorithm())
