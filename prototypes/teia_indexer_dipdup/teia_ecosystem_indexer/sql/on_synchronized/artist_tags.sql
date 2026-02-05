-- Summarize the top 10 tags for every artist based on their minted tokens
-- This helps categorize artists (e.g., "Glitch", "Photography", "PFP")
CREATE MATERIALIZED VIEW IF NOT EXISTS artist_tags_summary AS
WITH tagged_tokens AS (
    SELECT 
        t.creator_id,
        tg.name as tag,
        COUNT(*) as usage_count
    FROM token t
    JOIN token_tag tt ON t.id = tt.token_id
    JOIN tag tg ON tt.tag_id = tg.id
    GROUP BY t.creator_id, tg.name
),
ranked_tags AS (
    SELECT 
        creator_id,
        tag,
        usage_count,
        ROW_NUMBER() OVER(PARTITION BY creator_id ORDER BY usage_count DESC) as rank
    FROM tagged_tokens
)
SELECT 
    creator_id,
    tag,
    usage_count
FROM ranked_tags
WHERE rank <= 10;

CREATE UNIQUE INDEX IF NOT EXISTS idx_artist_tags_summary_creator_tag ON artist_tags_summary (creator_id, tag);
CREATE INDEX IF NOT EXISTS idx_artist_tags_summary_creator ON artist_tags_summary (creator_id);

-- Refresh this as part of the sync process
REFRESH MATERIALIZED VIEW CONCURRENTLY artist_tags_summary;
