BEGIN;

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    job_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    asset_signature VARCHAR(255) NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_analysis_jobs_asset_type_signature
    ON analysis_jobs (asset_id, job_type, asset_signature);

CREATE INDEX IF NOT EXISTS ix_analysis_jobs_status_created
    ON analysis_jobs (status, created_at);

ALTER TABLE document_analyses
    ADD COLUMN IF NOT EXISTS document_date TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS issue_date_source TEXT,
    ADD COLUMN IF NOT EXISTS expiry_date_source TEXT,
    ADD COLUMN IF NOT EXISTS expiry_confidence DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS issuing_organization VARCHAR(255);

COMMIT;
