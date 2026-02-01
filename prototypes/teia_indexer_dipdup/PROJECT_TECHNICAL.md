Teia Trust Network — Technical Notes (developer-facing)
Date: 2026-02-01
Status: Phase 1 (Foundation) — indexer running; recent fixes applied

Summary
-------
Concise, developer-focused reference for the DipDup indexer used by the Teia Trust Network.
This document consolidates previous agent notes and the repository's current, tested state.

Quick status
------------
- DipDup: v8.x (project generated with DipDup 8.5.1)
- Python: 3.12 (required)
- Runtime: Linux / WSL (uvloop recommended)
- DB: SQLite (dev) / Postgres (prod via compose+Hasura)
- Recent fixes (2026-02-01): defensive big-map diff parsing; robust swap_id normalization for collect handlers.

Why this exists
----------------
- Capture the canonical handler contracts, data-flow and recent runtime fixes so new devs/operators can get productive quickly.

Contract schemas & important shapes
-----------------------------------
- HEN V2 (hen_market_v2) & Teia (teia_market):
  - `swap` entrypoint → parameter contains `objkt_id`, `objkt_amount`, `xtz_per_objkt`, `royalties`, `creator`.
  - `collect` entrypoint → **single nat** (Swap ID) available as `parameter.root` (or `parameter` wrapped depending on codegen).
  - **Swap ID** is generated on-chain and appears in the contract `swaps` big_map — you must parse it from the BigMap diff (the new map key).

Key design (Trust graph)
-------------------------
1. on_swap: parse big-map diff → persist Swap (swap_id, seller, token_id, price, timestamp)
2. on_collect: read parameter.root → query Swap table → create TrustEdge (buyer -> seller)

Common pitfalls (and how we fixed them)
--------------------------------------
- Big-map diffs shape mismatch
  - Symptom: AttributeError: 'dict' object has no attribute 'action'
  - Root cause: DipDup / TZKT sometimes delivers big-map diffs as plain dicts (RPC) instead of typed model objects.
  - Fix (applied): handlers now accept both dict- and object-style diffs (use `diff.get('action')` or `getattr(diff, 'action', None)`).
  - Files patched: `handlers/on_swap.py`, `handlers/on_swap_teia.py`, `handlers/on_swap_v2.py`.

- Parameter object passed to ORM
  - Symptom: TypeError: int() argument must be ... not 'CollectParameter'
  - Root cause: code passed the generated Pydantic parameter object directly into a Tortoise IntField.
  - Fix (applied): collect handlers normalize the `swap_id` into `int | None` before DB usage.
  - Files patched: `handlers/on_collect.py`, `handlers/on_collect_teia.py` (+ related handlers reviewed).

Current code patterns (important to follow)
-------------------------------------------
- Always normalize shapes coming from `transaction.parameter` and `transaction.data.diffs` before using them in DB queries.
- Prefer defensive access in handlers:
  - action = diff.get('action') if isinstance(diff, dict) else getattr(diff, 'action', None)
  - key = diff.get('key') if isinstance(diff, dict) else getattr(diff, 'key', None)
- When resolving swap id, accept: int, numeric string, dict with `root`/`__root__`/`swap_id`, or pydantic wrapper.

Files of interest (where logic lives)
-------------------------------------
- handlers/
  - `on_swap.py` — shared swap logic (robust example)
  - `on_swap_teia.py`, `on_swap_v2.py` — market-specific swap handlers
  - `on_collect.py`, `on_collect_teia.py` — collect handlers (now normalize swap_id)
- models/__init__.py — Swap, Trade, TrustEdge
- schema_sniffer_out.txt — canonical contract schemas used during development

How to run (developer) — quick
-----------------------------
# In WSL / Linux environment
cd prototypes/teia_indexer_dipdup/teia_ecosystem_indexer
# Run (dev)
dipdup run
# Run with SQLite (local DB)
dipdup -C sqlite run
# Use helper to check progress
uv run check_indexer_progress.py

Operational verification (use while syncing)
--------------------------------------------
- Logs: look for `Synchronizing index to level` and then `synced`.
- Handler activity (examples):
  - `🏷️  SAVED SWAP #<id>`
  - `💰 EDGE CREATED: <buyer> -> <seller> ...`
- DB queries (sqlite):
  - `sqlite3 teia_trust.sqlite3 "SELECT count(*) FROM swap;"`
  - `sqlite3 teia_trust.sqlite3 "SELECT * FROM trustedge ORDER BY timestamp DESC LIMIT 10;"`
- DipDup crash reports:
  - `dipdup report show <report_id>`

Dependencies / environment notes
--------------------------------
- Python 3.12 is required (project codegen and DipDup compatibility). Do not run under 3.11.
- uvloop recommended (Linux/WSL). Avoid running DipDup without an async loop optimised for production.
- Tortoise ORM + aiosqlite: pin `aiosqlite<0.20` to avoid incompatibilities.

Recent changelog (2026-02-01)
-----------------------------
- Defensive parsing added for big-map diffs (both dict & object shapes).
- swap_id normalization added to collect handlers to avoid ORM TypeErrors.
- Project docs (PROJECT.md / README.md) updated with runbook and verification steps.

Tests & next technical work (recommended)
----------------------------------------
Priority (high → low):
1. Add unit tests for handlers that feed both dict- and object-shaped `diff` and `parameter` inputs. (Protects regressions.)
2. Centralize normalization helpers (e.g. `teia_ecosystem_indexer.utils.normalize`) and replace duplicated code in handlers.
3. Add CI job that runs handler-level unit tests with synthetic Tezos messages (fast, isolated).
4. Add lightweight monitoring script to expose: index level vs tzkt head, recent handler events/sec, last processed timestamp.

Suggested short-term PR
-----------------------
- Create `tests/handlers/test_collect_and_swap.py` with parameterized cases for:
  - dict-diff, object-diff for `on_swap` handlers
  - wrapped `parameter` object vs raw `nat` for `on_collect`
- Factor `_normalize_swap_id` into `utils` and update handlers to import it.

If you want, I can open that PR (include tests + helper refactor) and draft the CI job.

Contact points / where to look for regressions
----------------------------------------------
- Logs in the terminal running `dipdup run`
- DipDup reports (`dipdup report show <id>`)
- Database (sqlite) rows for `swap` and `trustedge`


-----
This file is current with the repository as of 2026-02-01 and reflects the fixes applied in our recent session (defensive diff handling and swap_id normalization).