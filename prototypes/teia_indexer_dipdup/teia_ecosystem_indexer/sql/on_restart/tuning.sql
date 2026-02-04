-- 1. BRIN Indexes for Temporal Data (Resilient)
CREATE INDEX IF NOT EXISTS idx_trade_timestamp_brin ON trade USING BRIN (timestamp);
CREATE INDEX IF NOT EXISTS idx_transfer_timestamp_brin ON transfer USING BRIN (timestamp);
CREATE INDEX IF NOT EXISTS idx_swap_timestamp_brin ON swap USING BRIN (timestamp);

-- 2. Covering Identity Index (Zero-IO)
CREATE UNIQUE INDEX IF NOT EXISTS idx_holder_address_id_covering ON holder (address, id);

-- 3. Market Optimization: Partial Index for Active Swaps
CREATE INDEX IF NOT EXISTS idx_swaps_active_price ON swap (price_mutez) WHERE status = 'active';

-- 4. Drop redundant indexes (handled now by unique_together constraints)
DROP INDEX IF EXISTS token_holder_token_id_idx;
DROP INDEX IF EXISTS token_tag_token_id_idx;
DROP INDEX IF EXISTS signature_token_id_idx;
DROP INDEX IF EXISTS shareholder_split_contract_id_idx;

-- 5. Data Hygiene: Purge zero-quantity balances
DELETE FROM token_holder WHERE quantity <= 0;

-- 6. Maintenance: Analyze high-churn tables
ANALYZE trade;
ANALYZE token_holder;
