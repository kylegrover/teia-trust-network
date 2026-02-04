-- Ensure the Trust Network aggregates exist before refreshing
-- This handles the case where on_restart scripts might have failed due to missing tables
CREATE MATERIALIZED VIEW IF NOT EXISTS trust_connections AS
SELECT
    buyer_id AS source_id,
    creator_id AS target_id,
    COUNT(*) AS trade_count,
    SUM(price_mutez) AS total_volume_mutez,
    MIN(timestamp) AS first_interaction,
    MAX(timestamp) AS last_interaction
FROM trade
GROUP BY buyer_id, creator_id;

-- Ensure lookups on the view are fast
CREATE UNIQUE INDEX IF NOT EXISTS idx_trust_connections_source_target ON trust_connections (source_id, target_id);

-- Refresh the Trust Network aggregates once we hit head
REFRESH MATERIALIZED VIEW CONCURRENTLY trust_connections;
