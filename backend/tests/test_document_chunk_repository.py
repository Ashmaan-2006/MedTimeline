from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from medgraph_api.crud.document_chunks import DocumentChunkRepository
from medgraph_api.models.document_chunk import DocumentChunk
from medgraph_api.services.retrieval_filters import RetrievalFilters


class RecordingSession:
    def __init__(self) -> None:
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return self

    def all(self) -> list[DocumentChunk]:
        return []


def test_search_similar_for_patient_orders_by_vector_cosine_distance() -> None:
    session = RecordingSession()
    patient_id = uuid4()
    query_embedding = [0.0] * 384
    query_embedding[0] = 0.1
    query_embedding[1] = 0.2
    query_embedding[2] = 0.3

    results = DocumentChunkRepository(session).search_similar_for_patient(
        patient_id=patient_id,
        query_embedding=query_embedding,
        limit=7,
    )

    assert results == []
    assert session.statement is not None

    compiled = str(
        session.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "WHERE document_chunks.patient_id = " in compiled
    assert "document_chunks.embedding IS NOT NULL" in compiled
    assert "ORDER BY document_chunks.embedding <=>" in compiled
    assert "LIMIT 7" in compiled


def test_search_similar_for_patient_applies_document_and_date_filters() -> None:
    session = RecordingSession()
    patient_id = uuid4()
    document_id = uuid4()
    query_embedding = [0.0] * 384

    DocumentChunkRepository(session).search_similar_for_patient(
        patient_id=patient_id,
        query_embedding=query_embedding,
        filters=RetrievalFilters(
            document_id=document_id,
            created_from=datetime(2026, 1, 1, tzinfo=UTC),
            created_to=datetime(2026, 1, 31, 23, 59, tzinfo=UTC),
        ),
    )

    assert session.statement is not None

    compiled = str(
        session.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "document_chunks.patient_id = " in compiled
    assert "document_chunks.document_id = " in compiled
    assert "document_chunks.created_at >= '2026-01-01 00:00:00+00:00'" in compiled
    assert "document_chunks.created_at <= '2026-01-31 23:59:00+00:00'" in compiled
