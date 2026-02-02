-- 0002_drop_legacy_addresses.postgres.sql
-- DROP legacy address columns (creator_address, seller_address, buyer_address)
-- Run AFTER backfill and monitoring window. Ensure you have a DB backup.

BEGIN;

-- Sanity checks (abort if any of these return unexpected counts)
-- SELECT count(*) FROM token WHERE creator_id IS NULL;  -- expect 0
-- SELECT count(*) FROM swap WHERE seller_id IS NULL;    -- expect 0 or acceptable
-- SELECT count(*) FROM trade WHERE buyer_id IS NULL;    -- expect 0 or acceptable

ALTER TABLE token DROP COLUMN IF EXISTS creator_address;
ALTER TABLE "swap" DROP COLUMN IF EXISTS seller_address;
ALTER TABLE trade DROP COLUMN IF EXISTS buyer_address;

COMMIT;

-- ROLLBACK (manual):
-- 1) Add the columns back:
-- ALTER TABLE token ADD COLUMN creator_address VARCHAR(36);
-- ALTER TABLE "swap" ADD COLUMN seller_address VARCHAR(36);
-- ALTER TABLE trade ADD COLUMN buyer_address VARCHAR(36);
-- 2) Backfill from holder:
-- UPDATE token SET creator_address = h.address FROM holder h WHERE token.creator_id = h.id;
-- UPDATE "swap" SET seller_address = h.address FROM holder h WHERE "swap".seller_id = h.id;
-- UPDATE trade SET buyer_address = h.address FROM holder h WHERE trade.buyer_id = h.id;
-- 3) ANALYZE token; ANALYZE "swap"; ANALYZE trade;
