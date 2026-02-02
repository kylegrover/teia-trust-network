-- SQLite-friendly backfill for local/dev only
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS holder (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  address TEXT NOT NULL UNIQUE,
  first_seen DATETIME NULL,
  last_seen DATETIME NULL
);
CREATE INDEX IF NOT EXISTS idx_holder_address ON holder(address);

-- Add nullable FK integer columns (SQLite allows adding columns easily)
ALTER TABLE token   ADD COLUMN creator_id INTEGER;
ALTER TABLE "swap" ADD COLUMN seller_id INTEGER;
ALTER TABLE trade   ADD COLUMN buyer_id INTEGER;

-- Populate holder
INSERT OR IGNORE INTO holder(address)
  SELECT DISTINCT creator_address FROM token WHERE creator_address IS NOT NULL;
INSERT OR IGNORE INTO holder(address)
  SELECT DISTINCT seller_address FROM "swap" WHERE seller_address IS NOT NULL;
INSERT OR IGNORE INTO holder(address)
  SELECT DISTINCT buyer_address FROM trade WHERE buyer_address IS NOT NULL;

-- Backfill FK columns
UPDATE token SET creator_id = (SELECT id FROM holder WHERE holder.address = token.creator_address) WHERE creator_id IS NULL AND creator_address IS NOT NULL;
UPDATE "swap" SET seller_id = (SELECT id FROM holder WHERE holder.address = "swap".seller_address) WHERE seller_id IS NULL AND seller_address IS NOT NULL;
UPDATE trade SET buyer_id = (SELECT id FROM holder WHERE holder.address = trade.buyer_address) WHERE buyer_id IS NULL AND buyer_address IS NOT NULL;

COMMIT;
PRAGMA foreign_keys = ON;

-- Note: SQLite does not support adding FK constraints after-the-fact easily. For production use Postgres migration above.
