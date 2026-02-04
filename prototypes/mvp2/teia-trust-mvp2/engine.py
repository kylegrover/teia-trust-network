import asyncio
import networkx as nx
from database import get_db_conn
import time

async def init_score_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS trust_scores (
            holder_id INTEGER PRIMARY KEY REFERENCES holder(id),
            score FLOAT NOT NULL,
            rank INTEGER NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_trust_scores_rank ON trust_scores(rank);
    """)

async def run_trust_algorithm():
    print("🚀 Starting Trust Engine MVP2...")
    start_time = time.time()
    
    async with get_db_conn() as conn:
        await init_score_table(conn)
        
        # 1. Fetch edges from our optimized trust_connections view
        print("📥 Fetching trust connections...")
        rows = await conn.fetch("SELECT source_id, target_id, trade_count FROM trust_connections")
        
        if not rows:
            print("⚠️ No trust connections found. Is the indexer finished?")
            return

        # 2. Build the graph
        print(f"🏗️ Building graph from {len(rows)} connections...")
        G = nx.DiGraph()
        for r in rows:
            G.add_edge(r['source_id'], r['target_id'], weight=r['trade_count'])
            
        print(f"📊 Graph stats: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        # 3. Compute PageRank
        print("🧠 Computing PageRank (weighted)...")
        # alpha=0.85 is standard. personalization=None (unbiased)
        scores = nx.pagerank(G, alpha=0.85, weight='weight')
        
        # 4. Normalize and Rank
        max_score = max(scores.values()) if scores else 1.0
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # 5. Save to DB
        print(f"💾 Saving {len(sorted_scores)} scores to PostgreSQL...")
        
        # We'll use a transaction and temporary table for fast batch update
        await conn.execute("CREATE TEMP TABLE tmp_scores (holder_id INT, score FLOAT, rank INT)")
        
        batch = [
            (holder_id, (score / max_score) * 100, rank) 
            for rank, (holder_id, score) in enumerate(sorted_scores, 1)
        ]
        
        await conn.copy_records_to_table('tmp_scores', records=batch)
        
        async with conn.transaction():
            # Atomically swap or update
            await conn.execute("DELETE FROM trust_scores")
            await conn.execute("""
                INSERT INTO trust_scores (holder_id, score, rank)
                SELECT holder_id, score, rank FROM tmp_scores
            """)
            
    end_time = time.time()
    print(f"✅ Trust Engine completed in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    asyncio.run(run_trust_algorithm())
