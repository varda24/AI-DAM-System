BEGIN;

ALTER TABLE assets
    ADD COLUMN IF NOT EXISTS source_account_id TEXT;

ALTER TABLE assets
    ADD COLUMN IF NOT EXISTS web_view_link TEXT;

ALTER TABLE assets
    ADD COLUMN IF NOT EXISTS source_folder_id TEXT;

ALTER TABLE assets
    DROP CONSTRAINT IF EXISTS uq_asset_source_file;

ALTER TABLE assets
    DROP CONSTRAINT IF EXISTS ck_drive_assets_require_account;

ALTER TABLE assets
    ADD CONSTRAINT ck_drive_assets_require_account
    CHECK (source <> 'google_drive' OR source_account_id IS NOT NULL);

CREATE UNIQUE INDEX IF NOT EXISTS uq_assets_non_drive_source_file
    ON assets (source, source_file_id)
    WHERE source <> 'google_drive';

CREATE UNIQUE INDEX IF NOT EXISTS uq_assets_drive_account_file
    ON assets (source, source_account_id, source_file_id)
    WHERE source = 'google_drive';

COMMIT;
