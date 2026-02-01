Indexer for tokens, holders and market history (snapshot + backfill).

Run: uv run teia_indexer.py
Output: teia_index.db (tables: tokens, holders, events, state)
Good for snapshots and history; does not emit trust graph or reputation scores
Next: expose events → edges transform and add provenance joins
