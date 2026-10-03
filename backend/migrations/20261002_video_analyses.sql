BEGIN;

CREATE TABLE IF NOT EXISTS video_analyses (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL UNIQUE,
    duration_seconds DOUBLE PRECISION,
    width INTEGER,
    height INTEGER,
    fps DOUBLE PRECISION,
    frame_count INTEGER,
    video_codec VARCHAR(32),
    thumbnail_path TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'analyzed',
    error_message TEXT,
    analyzed_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_video_analyses_asset_id
    ON video_analyses (asset_id);

COMMIT;