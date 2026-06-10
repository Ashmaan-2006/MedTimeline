BEGIN;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS processing_status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
    ADD COLUMN IF NOT EXISTS processing_error TEXT,
    ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS processing_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS processing_attempts INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_documents_processing_status
    ON documents (processing_status);

CREATE INDEX IF NOT EXISTS ix_documents_celery_task_id
    ON documents (celery_task_id);

COMMIT;
