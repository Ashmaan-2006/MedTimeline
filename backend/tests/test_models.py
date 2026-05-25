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
