# Teia Trust MVP2

Second iteration of the Teia Trust Network prototype, now powered by the production-grade PostgreSQL indexer.

## Key Upgrades
- **Database**: Shifted from SQLite to **PostgreSQL**.
- **Data Source**: Uses the `trust_connections` materialized view (5 years of history).
- **Identity**: Resolves aliases and avatars from `holder_metadata`.
- **Ranking**: Global PageRank now weights connections by `trade_count`.
- **Scale**: Optimized for millions of rows using PostgreSQL composite indexes.

## Components
- `engine.py`: Runs the PageRank algorithm and saves global trust scores.
- `main.py`: FastAPI backend for trust queries and graph visualization data.
- `database.py`: Shared postgres connection logic.

## Setup
1. Ensure the `teia_ecosystem` database is running and indexed.
2. Run the engine to compute scores:
   ```bash
   uv run engine.py
   ```
3. Start the API:
   ```bash
   uv run uvicorn main:app --reload
   ```
