# trust_engine.py
import networkx as nx
from database import get_db, init_db

def run_trust_algorithm():
    print("🧠 Starting Trust Calculation Engine...")
    db = get_db()
    
    # 1. Load Data into Memory
    print("   Loading graph data...")
    edges = list(db["edges"].rows)
    if not edges:
        print("   ⚠️ No data found. Run indexer first.")
        return

    # 2. Build the Graph
    G = nx.DiGraph()
    
    for e in edges:
        u = e["source"]
        v = e["target"]
        
        # We assume every collect adds "weight" to the trust relationship
        if G.has_edge(u, v):
            G[u][v]['weight'] += 1
        else:
            G.add_edge(u, v, weight=1)

    print(f"   Graph Built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")

    # 3. Run PageRank (The Core Algorithm)
    # alpha=0.85 means there's a 15% chance of jumping to a random node (damping factor)
    # We use 'weight' so buying 10 items is stronger than buying 1.
    print("   Computing PageRank...")
    scores = nx.pagerank(G, alpha=0.85, weight='weight')

    # 4. Normalize and Store
    # We verify the top score to normalize everyone else against it (0-100 scale usually better for UI)
    if scores:
        max_score = max(scores.values())
    else:
        max_score = 1.0

    print("   Saving scores to DB...")
    
    # Prepare batch for insertion
    batch_data = []
    # Sort by score desc to assign rank
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    for rank, (address, raw_score) in enumerate(sorted_items, 1):
        # Normalize to 0-100 for human readability
        normalized_score = (raw_score / max_score) * 100
        
        batch_data.append({
            "address": address,
            "score": normalized_score,
            "rank": rank
        })

    # Upsert into DB (Replace old scores)
    db["scores"].insert_all(batch_data, pk="address", replace=True)
    
    print(f"✅ Calculated scores for {len(batch_data)} users.")
    print(f"   🏆 Top Trust: {sorted_items[0][0]} (Score: 100)")

if __name__ == "__main__":
    init_db()
    run_trust_algorithm()