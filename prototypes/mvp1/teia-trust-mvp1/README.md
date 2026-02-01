How to Run

### Setup

dependencies

uv add fastapi uvicorn httpx sqlite-utils

**1** Seed the Data:

`uv run indexer.py`

Watch the logs. It should say "Found X collect events" then "Mapped Y trust connections".

**2** Verify Data (SQL Check): Run this to see a real connection you just indexed:

`uv run python -c "from database import db; print(list(db['edges'].rows)[0])"`

**3** Start API:

`uv run uvicorn main:app --reload`


Calculate Scores: Run the math engine. (You run this whenever you want to update reputations).
Bash

uv run trust_engine.py

(You should see "🏆 Top Trust: tz1..." with the highest authority in your dataset).


Visualize: Reload your viz.html.

    New Feature: High-reputation nodes (the curators and popular artists) will now appear physically larger than random users. Hover over a node to see its calculated "Trust Score".