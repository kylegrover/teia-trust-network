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