-- 1. BRIN Indexes for Temporal Data
-- These are tiny (KB range instead of MB) and perfect for naturally ordered blockchain data.
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'trade') THEN
        CREATE INDEX IF NOT EXISTS idx_trade_timestamp_brin ON trade USING BRIN (timestamp);
    END IF;
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'transfer') THEN
        CREATE INDEX IF NOT EXISTS idx_transfer_timestamp_brin ON transfer USING BRIN (timestamp);
    END IF;
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'swap') THEN
        CREATE INDEX IF NOT EXISTS idx_swap_timestamp_brin ON swap USING BRIN (timestamp);
    END IF;
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'holder') THEN
        CREATE UNIQUE INDEX IF NOT EXISTS idx_holder_address_id_covering ON holder (address, id);
    END IF;
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'swap') THEN
         CREATE INDEX IF NOT EXISTS idx_swaps_active_price ON swap (price_mutez) WHERE status = 'active';
    END IF;
END
$$;

-- 4. Trust Relationship Derivative (Materialized View)
-- This calculates the "Trust Network" aggregates without needing a reindex.
-- Wrap in a block or use IF NOT EXISTS to prevent blocking restarts if tables are missing
-- (Final robust creation happens in on_synchronized)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'trade') THEN
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

        IF NOT EXISTS (SELECT indexname FROM pg_indexes WHERE indexname = 'idx_trust_connections_source_target') THEN
            CREATE UNIQUE INDEX idx_trust_connections_source_target ON trust_connections (source_id, target_id);
        END IF;
    END IF;
END
$$;

-- Optional: If the user has permission, we can suggest REFRESH in a separate hook.
