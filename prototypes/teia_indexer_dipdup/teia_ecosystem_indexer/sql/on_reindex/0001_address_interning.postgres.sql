-- 0001_address_interning.postgres.sql
-- Postgres migration to introduce a compact `holder` (identity) table
-- Safe rollout: add nullable FK columns, backfill from legacy string columns, then add FK constraints.

BEGIN;

-- 1) Create identity registry
CREATE TABLE IF NOT EXISTS holder (
  id          BIGSERIAL PRIMARY KEY,
  address     VARCHAR(36) NOT NULL UNIQUE,
  first_seen  TIMESTAMP WITH TIME ZONE NULL,
  last_seen   TIMESTAMP WITH TIME ZONE NULL
);
CREATE INDEX IF NOT EXISTS idx_holder_address ON holder(address);

-- 2) Add nullable FK columns to host tables (safe, non-blocking)
ALTER TABLE "token"   ADD COLUMN IF NOT EXISTS creator_id BIGINT;
ALTER TABLE "swap"    ADD COLUMN IF NOT EXISTS seller_id  BIGINT;
ALTER TABLE "trade"   ADD COLUMN IF NOT EXISTS buyer_id   BIGINT;

-- 3) Populate holder from existing string columns (idempotent)
INSERT INTO holder(address)
  SELECT DISTINCT creator_address FROM token WHERE creator_address IS NOT NULL
  ON CONFLICT DO NOTHING;
INSERT INTO holder(address)
  SELECT DISTINCT seller_address FROM "swap" WHERE seller_address IS NOT NULL
  ON CONFLICT DO NOTHING;
INSERT INTO holder(address)
  SELECT DISTINCT buyer_address FROM "trade" WHERE buyer_address IS NOT NULL
  ON CONFLICT DO NOTHING;

-- 4) Backfill FK columns
UPDATE token SET creator_id = h.id
  FROM holder h WHERE h.address = token.creator_address AND token.creator_id IS NULL;
UPDATE "swap" SET seller_id = h.id
  FROM holder h WHERE h.address = "swap".seller_address AND "swap".seller_id IS NULL;
UPDATE "trade" SET buyer_id = h.id
  FROM holder h WHERE h.address = "trade".buyer_address AND "trade".buyer_id IS NULL;

-- 5) Add FK constraints (will fail if referential integrity isn't satisfied)
ALTER TABLE token ADD CONSTRAINT token_creator_fk FOREIGN KEY (creator_id) REFERENCES holder(id);
ALTER TABLE "swap" ADD CONSTRAINT swap_seller_fk FOREIGN KEY (seller_id) REFERENCES holder(id);
ALTER TABLE "trade" ADD CONSTRAINT trade_buyer_fk FOREIGN KEY (buyer_id) REFERENCES holder(id);

COMMIT;

-- NOTE: After running this migration in production, run application for a period to ensure no missing edges,
-- then (in a follow-up migration) remove legacy string columns (`creator_address`, `seller_address`, `buyer_address`).
