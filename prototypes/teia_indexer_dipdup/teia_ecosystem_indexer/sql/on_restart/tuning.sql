-- 1. BRIN Indexes for Temporal Data
-- These are tiny (KB range instead of MB) and perfect for naturally ordered blockchain data.
CREATE INDEX IF NOT EXISTS idx_trade_timestamp_brin ON trade USING BRIN (timestamp);
CREATE INDEX IF NOT EXISTS idx_transfer_timestamp_brin ON transfer USING BRIN (timestamp);
CREATE INDEX IF NOT EXISTS idx_swap_timestamp_brin ON swap USING BRIN (timestamp);

-- 2. Covering Identity Index (Zero-IO)
-- This allows resolving address -> id without hitting the main table heap.
CREATE UNIQUE INDEX IF NOT EXISTS idx_holder_address_id_covering ON holder (address, id);

-- 3. Market Optimization: Partial Index for Active Swaps
-- Most marketplace queries only care about ACTIVE listings. This index will be tiny.
CREATE INDEX IF NOT EXISTS idx_swaps_active_price ON swap (price_mutez) WHERE status = 'active';

-- 4. Trust Relationship Derivative (Materialized View)
-- This calculates the "Trust Network" aggregates without needing a reindex.
-- It can be refreshed periodically without DipDup knowing about it.
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

-- Optional: If the user has permission, we can suggest REFRESH in a separate hook.
