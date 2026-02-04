-- Refresh the Trust Network aggregates once we hit head
REFRESH MATERIALIZED VIEW CONCURRENTLY trust_connections;
