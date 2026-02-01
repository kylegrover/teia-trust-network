# Teia/HEN Local Indexer Project

**Date:** January 31, 2026
**Status:** In Progress (Phase 1 & 2 Running)

## 1. Project Overview

This project is a lightweight, domain-specific indexer for the **Teia and Hic et Nunc (HEN)** ecosystem on Tezos. Unlike general-purpose indexers (TzKT), this tool flattens blockchain data into a business-logic schema optimized for the art marketplace.

It allows for SQL querying of:

* **Inventory:** All OBJKTs ever minted.
* **Ownership:** Who owns what right now (Ledger).
* **Market History:** Every sale, listing, and cancellation from HEN v1, v2, and Teia.

## 2. Architecture

The system consists of two independent Python scripts sharing a single SQLite database.

* **`teia_indexer.py` (The "Node"):**
* **Role:** Handles all Blockchain interaction.
* **Phase 1 (Snapshot):** Downloads the *current* state of Tokens and Holders from BigMaps.
* **Phase 2 (History/Stream):** Backfills historical sales events and listens for new operations.


* **`metadata_worker.py` (The "Enricher"):**
* **Role:** Handles all IPFS interaction.
* **Function:** Scans the DB for tokens with `Unknown` titles, fetches the JSON from IPFS gateways, and updates the database with Titles, Royalties, and Artifact links.



## 3. Current Status

### ✅ Completed

* **Database Schema:** Defined in SQLite (`tokens`, `holders`, `events`, `state`).
* **Phase 1 (Snapshot):**
* Fixed `StopIteration` crash by adding robust BigMap ID discovery.
* Implemented "Resumability" (saves `token_offset` and `holder_offset` to DB).
* *State:* Currently running/ready to resume.


* **Phase 2 (History):**
* Logic implemented to fetch historical `collect` and `swap` events.
* Resumable via `last_op_id`.


* **Metadata Worker:**
* Script written (`metadata_worker.py`) with gateway rotation and concurrency.



### ⏳ In Progress / To-Do

1. **Finish Phase 1 Sync:** Allow `teia_indexer.py` to finish downloading the ~850k token keys and ~2m ledger entries.
2. **Start Phase 2 Backfill:** Once Phase 1 is done, the script will automatically switch to downloading history.
3. **Run Metadata Worker:** Needs to be started in a separate terminal to begin resolving `ipfs://` links.

## 4. How to Resume

### Step 1: Run the Indexer

This handles the "hard data" from the blockchain. It is safe to stop (`Ctrl+C`) and restart at any time.

```bash
# Terminal 1
uv run teia_indexer.py

```

* **Expected Output:** `🔄 Resuming Token Sync from offset X...` or `👥 Starting Holder Sync...`
* **Goal:** Wait until it says `✅ Holdings Synced`. It will then automatically start "Phase 2: History".

### Step 2: Run the Metadata Worker (Optional but Recommended)

You can run this **simultaneously** with Step 1, or wait until Step 1 is done. It fills in the "Unknown" titles in your database.

```bash
# Terminal 2
uv run metadata_worker.py

```

* **Expected Output:** `✅ Processed batch. Total this session: 50...`

## 5. Helpful Commands (SQL)

Use **DB Browser for SQLite** or the command line to check progress.

**Check Sync Progress:**

```sql
SELECT 
    (SELECT count(*) FROM tokens) as total_tokens,
    (SELECT count(*) FROM holders) as total_holders,
    (SELECT count(*) FROM events) as total_sales,
    (SELECT value FROM state WHERE key='token_offset') as current_offset;

```

**Calculate Total Volume (Tez):**

```sql
SELECT sum(price_mutez) / 1000000.0 as volume_tez 
FROM events 
WHERE type = 'SALE';

```

**Find "Whales" (Top Collectors):**

```sql
SELECT address, sum(amount) as objkts_owned 
FROM holders 
GROUP BY address 
ORDER BY objkts_owned DESC 
LIMIT 10;

```