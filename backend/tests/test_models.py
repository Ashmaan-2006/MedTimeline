from medgraph_api.db.base import Base


def test_initial_database_models_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "document_chunks",
        "documents",
        "patients",
        "timeline_events",
    }


def test_document_chunk_model_uses_vector_embedding_column() -> None:
    embedding_column = Base.metadata.tables["document_chunks"].columns["embedding"]

    assert str(embedding_column.type) == "VECTOR(384)"


def test_document_chunk_model_includes_embedding_metadata_columns() -> None:
    chunk_table = Base.metadata.tables["document_chunks"]

    assert {"embedding_model", "token_count", "chunk_metadata"}.issubset(chunk_table.columns.keys())


def test_document_model_includes_processing_state_columns() -> None:
    document_table = Base.metadata.tables["documents"]

    assert {
        "processing_status",
        "processing_error",
        "processing_started_at",
        "processing_completed_at",
        "celery_task_id",
        "processing_attempts",
    }.issubset(document_table.columns.keys())
