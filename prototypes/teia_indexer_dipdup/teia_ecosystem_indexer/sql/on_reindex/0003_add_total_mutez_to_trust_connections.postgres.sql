-- 0003_add_total_mutez_to_trust_connections.postgres.sql
-- Ensure `trust_connections` exposes `total_mutez` (price_mutez * amount) for the trust engine.
-- Safe to run on a COPY of the DB during controlled reindex; non-destructive for Postgres when used with CREATE OR REPLACE.

CREATE OR REPLACE MATERIALIZED VIEW trust_connections AS
SELECT
  buyer_id        AS source_id,
  creator_id      AS target_id,
  COUNT(*)        AS trade_count,
  SUM(price_mutez) AS total_volume_mutez,
  SUM(price_mutez * COALESCE(amount, 1)) AS total_mutez,
  MIN(timestamp)  AS first_interaction,
  MAX(timestamp)  AS last_interaction
FROM trade
WHERE buyer_id IS NOT NULL AND creator_id IS NOT NULL
GROUP BY buyer_id, creator_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_trust_connections_source_target ON trust_connections (source_id, target_id);
CREATE INDEX IF NOT EXISTS idx_trust_connections_total_mutez ON trust_connections (total_mutez);

-- If the materialized view already exists, callers should REFRESH MATERIALIZED VIEW CONCURRENTLY trust_connections
-- after the migration is applied (or during normal reindex flow).