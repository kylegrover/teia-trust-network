# **Teia Decentralized Trust Network: Phase 0 Prototype**

**Status Report - Jan 31, 2026**

### **1. Project Overview**

We are building a subjective, decentralized reputation system for the Teia art ecosystem on Tezos. Instead of a centralized "Verified" list, this system calculates a dynamic "Trust Score" based on on-chain provenance (who collects whom).

**Current Phase:** Phase 0 (Local MVP)
**Goal:** Prove the "Data  Trust Signal" loop locally without complex infrastructure.

---

### **2. Architecture (Current Implementation)**

The system runs locally on a simple Python stack, using `uv` for dependency management.

* **Indexer (`indexer.py`):**
* **Strategy:** "Deterministic Trace." It fetches `collect` operations from TzKT, finds the associated internal Operation Group ID, and links it to the resulting Token Transfer. This guarantees we only index legitimate sales (money changed hands).
* **Sync Mode:** "Forward Sync." It starts from the Genesis of the contract (or the last saved ID) and crawls forward in time using a cursor stored in SQLite.
* **Contracts Tracked:**
* `HEN_V2` (Historical Hic et Nunc)
* `TEIA_MARKET` (Current Marketplace)




* **Database (`trust_network.db` - SQLite):**
* `edges`: Stores the graph connections (`source`, `target`, `token_id`, `timestamp`).
* `state`: Stores the synchronization cursor (`last_processed_id`) to allow pausing/resuming.
* `scores` (Prepared): Schema exists for PageRank scores, but population script is manual.


* **API (`main.py` - FastAPI):**
* `GET /trust/{observer}/{target}`: Returns a "Green" signal if a direct collection exists, "Yellow" otherwise. Also returns Global Trust Score/Rank if calculated.
* `GET /graph/{address}`: Returns a JSON node/edge list for "Friend-of-Friend" visualization.
* `GET /stats`: Returns system health metrics (total edges, sample data).


* **Frontend Tools:**
* `viz.html`: A standalone HTML tool using **Vis.js** to render interactive trust graphs.
* `test_widget.html`: A minimal UI to test the Trust Badge signal.



---

### **3. Current Status**

* **✅ Core Infrastructure:** The FastAPI server and SQLite database are fully functional and thread-safe.
* **✅ Data Integrity:** The "Genesis Block" bug was solved. The indexer now correctly traces internal operations, ignoring unrelated transfers.
* **✅ Synchronization:** The indexer is currently running in "Backfill Mode," crawling history starting from ~March 2021.
* *Current Progress:* ~500-1000 operations indexed (Local prototype scale).
* *Sync Status:* Catching up to present day.


* **✅ Visualization:** The `viz.html` tool successfully pulls data from the local API and renders the network graph.

---

### **4. Immediate Next Steps (To-Do)**

1. **Identity Layer (Enrichment):**
* **Why:** The graph is currently a "Hash Soup" of `tz1...` addresses.
* **Task:** Write `enricher.py` to query TzKT/Tezos Domains for aliases (e.g., "objkt.com", "primal_cyber") and populate a `profiles` table.


2. **Trust Score Math:**
* **Why:** We have the `trust_engine.py` script prepared (PageRank), but we need more data volume from the indexer before the scores become meaningful.
* **Task:** Let the indexer run overnight (or for a few hours) to get ~10k+ edges, then run `uv run trust_engine.py`.


3. **UI Integration:**
* **Why:** To see the badge in context.
* **Task:** Port the logic from `test_widget.html` into the actual React `Teia-UI` codebase (Phase 2 of Master Plan).



---

### **5. Quick Start (How to Resume)**

**1. Resume Indexing (Data Collection)**
Open a terminal and let this run in the background to gather more history.

```bash
cd teia-trust-mvp
uv run indexer.py

```

**2. Start the API Server**
Open a second terminal.

```bash
uv run uvicorn main:app --reload

```

**3. Check Progress**
See how close you are to real-time data.

```bash
uv run check_progress.py

```

**4. Visualize**
Open `viz.html` in your browser and enter a known collector address (e.g., one found via `http://localhost:8000/stats`).