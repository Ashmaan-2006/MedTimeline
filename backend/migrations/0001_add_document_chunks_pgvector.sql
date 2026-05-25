BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(384),
    embedding_model VARCHAR(100),
    token_count INTEGER,
    chunk_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_document_chunks_document_index UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS ix_document_chunks_patient_id
    ON document_chunks (patient_id);

CREATE INDEX IF NOT EXISTS ix_document_chunks_document_id
    ON document_chunks (document_id);

CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_cosine
    ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

COMMIT;

