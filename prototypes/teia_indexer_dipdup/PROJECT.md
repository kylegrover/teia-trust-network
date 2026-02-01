Contract Master Schema

Here is the "Mental Map" of the contracts you are indexing. Keep this handy for your Trust Engine logic.
Contract	DipDup Name	Entrypoint	Input Shape (Python)	What it means
HEN V2	hen_v2	collect	parameter.root (int)	"I am buying Swap #root"
Teia	teia_market	collect	parameter.root (int)	"I am buying Swap #root"
HEN V2	hen_v2	swap	objkt_id, xtz_per_objkt	"I am listing Token #objkt_id"
Teia	teia_market	swap	objkt_id, xtz_per_objkt	"I am listing Token #objkt_id"

see schema_sniffer_out.txt for full schema

---

## Operations runbook (DipDup) ✅

Quick checklist to run, verify and triage the DipDup indexer for this project.

### Start / Restart
- Development (in-process): `dipdup run` or `uv run teia_indexer.py`
- SQLite (local): `dipdup -C sqlite run` (set `SQLITE_PATH` to change DB file)
- Docker/Compose: `make up` (edit `deploy/.env` first)

### Quick verification (smoke tests)
1. Confirm sync progress in the indexer logs (look for `synchronizing` → `synced`).
2. Tail for handler events (examples): `🏷️  SAVED SWAP #...`, `💰 EDGE CREATED: ...`.
3. Check DB rows (sqlite example):
   - `sqlite3 teia_trust.sqlite3 "SELECT count(*) FROM swap;"`
   - `sqlite3 teia_trust.sqlite3 "SELECT * FROM swap ORDER BY timestamp DESC LIMIT 5;"`
4. Use `uv run check_indexer_progress.py` — returns 0 when basic progress checks pass.

### Common errors & fixes (recent) ⚠️
- AttributeError: `'dict' object has no attribute 'action'` — caused by DipDup sometimes delivering big-map diffs as plain dicts (RPC) instead of model objects. Fix: handlers now accept both dict- and object-style diffs (`diff.get(...)` or `getattr(...)`).
- TypeError: `int() argument must be ... not 'CollectParameter'` — caused by passing a parameter object directly to the ORM. Fix: collect handlers now normalize `swap_id` to an `int | None` before any DB call.

### How to triage a handler crash
1. Run the indexer and copy the full traceback (DipDup prints a report id you can run with `dipdup report show <id>`).
2. Grep for the handler name in `handlers/` and inspect parameter/diff access patterns.
3. If the crash is due to shape mismatch, add normalization (see `on_swap.py` and `on_collect.py` for examples).

### Recommended follow-ups (short)
- Add unit/integration tests that feed both dict- and object-shaped diffs/params to all handlers. ✅
- Centralize diff/param normalization into `teia_ecosystem_indexer.utils` and reuse across handlers. ✅
- Add a small monitoring query (or Grafana panel) that shows index level vs tzkt head and recent handler activity.

---

## Recent changes (summary)
- Defensive diff parsing for swap handlers (`on_swap*.py`) — prevents AttributeError on dict diffs.
- Robust swap_id normalization in collect handlers — prevents Tortoise TypeError when parameter objects are passed.
- Added developer runbook & verification steps (this section).

---

## TODO (short)
- Add tests that simulate RPC dict diffs and DipDup model diffs for all handlers.
- Move normalization logic into a shared util and update handlers to use it.
- Add CI checks that run handler-level unit tests on synthetic Tezos messages.

