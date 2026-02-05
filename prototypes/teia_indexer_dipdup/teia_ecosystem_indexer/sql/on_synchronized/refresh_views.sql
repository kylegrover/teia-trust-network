-- Ensure the Trust Network aggregates exist before refreshing
-- This handles the case where on_restart scripts might have failed due to missing tables
CREATE MATERIALIZED VIEW IF NOT EXISTS trust_connections AS
SELECT
    buyer_id AS source_id,
    creator_id AS target_id,
    COUNT(*) AS trade_count,
    -- legacy: total_volume_mutez (sum of per-unit price_mutez)
    SUM(price_mutez) AS total_volume_mutez,
    -- preferred: total_mutez (price * amount) — used by the trust engine
    SUM(price_mutez * COALESCE(amount, 1)) AS total_mutez,
    MIN(timestamp) AS first_interaction,
    MAX(timestamp) AS last_interaction
FROM trade
WHERE buyer_id IS NOT NULL AND creator_id IS NOT NULL
GROUP BY buyer_id, creator_id;

-- Ensure lookups on the view are fast
CREATE UNIQUE INDEX IF NOT EXISTS idx_trust_connections_source_target ON trust_connections (source_id, target_id);
CREATE INDEX IF NOT EXISTS idx_trust_connections_total_mutez ON trust_connections (total_mutez);

-- Refresh the Trust Network aggregates once we hit head
REFRESH MATERIALIZED VIEW CONCURRENTLY trust_connections;
