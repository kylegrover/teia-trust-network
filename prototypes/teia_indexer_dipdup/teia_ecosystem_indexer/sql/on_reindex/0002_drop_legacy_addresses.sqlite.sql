-- 0002_drop_legacy_addresses.sqlite.sql
-- Drop legacy address string columns in SQLite by recreating tables without them.
-- IMPORTANT: run on a COPY of the DB. This script is destructive and intended for a
-- controlled rollout AFTER `creator_id` / `seller_id` / `buyer_id` are fully populated.

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- TOKEN: remove creator_address (keep creator_id)
CREATE TABLE IF NOT EXISTS token_new AS
  SELECT id, contract, token_id, creator_id, supply, metadata_uri, metadata, metadata_synced, timestamp
  FROM token;
DROP TABLE token;
ALTER TABLE token_new RENAME TO token;

-- SWAP: remove seller_address (keep seller_id)
CREATE TABLE IF NOT EXISTS swap_new AS
  SELECT id, swap_id, contract_address, market_version, seller_id, token, amount_initial, amount_left, price_mutez, royalties_permille, status, timestamp
  FROM "swap";
DROP TABLE "swap";
ALTER TABLE swap_new RENAME TO "swap";

-- TRADE: remove buyer_address (keep buyer_id)
CREATE TABLE IF NOT EXISTS trade_new AS
  SELECT id, swap_id, buyer, amount, price_mutez, timestamp
  FROM trade;
DROP TABLE trade;
ALTER TABLE trade_new RENAME TO trade;

COMMIT;
PRAGMA foreign_keys = ON;

-- NOTE: this is irreversible in SQLite without a backup. Keep backup copies and verify the
-- application thoroughly before deleting originals.
