from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from medgraph_api.services.embeddings import HashingEmbeddingService
from medgraph_api.services.similarity_search import PatientDocumentSimilaritySearchService


@dataclass
class FakeDocumentChunk:
    id: UUID
    document_id: UUID
    patient_id: UUID
    chunk_index: int
    content: str
    embedding_model: str | None
    token_count: int | None
    chunk_metadata: dict | None
    created_at: datetime


class FakeDocumentChunkRepository:
    def __init__(self, chunks: list[FakeDocumentChunk] | None = None) -> None:
        self.chunks = chunks or []
        self.last_patient_id: UUID | None = None
        self.last_query_embedding: list[float] | None = None
        self.last_limit: int | None = None

    def search_similar_for_patient(
        self,
        patient_id: UUID,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[FakeDocumentChunk]:
        self.last_patient_id = patient_id
        self.last_query_embedding = query_embedding
        self.last_limit = limit
        return self.chunks[:limit]


def test_search_embeds_query_and_returns_ranked_chunk_results() -> None:
    patient_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    created_at = datetime.now(UTC)
    repository = FakeDocumentChunkRepository(
        chunks=[
            FakeDocumentChunk(
                id=chunk_id,
                document_id=document_id,
                patient_id=patient_id,
                chunk_index=2,
                content="Troponin elevation followed chest discomfort.",
                embedding_model="local-hashing-embedding-v1",
                token_count=5,
                chunk_metadata={"char_start": 100, "char_end": 145},
                created_at=created_at,
            )
        ]
    )

    results = PatientDocumentSimilaritySearchService(
        document_chunks=repository,
        embedding_service=HashingEmbeddingService(),
    ).search(
        patient_id=patient_id,
        query="Why did chest pain worsen?",
        limit=3,
    )

    assert repository.last_patient_id == patient_id
    assert repository.last_limit == 3
    assert repository.last_query_embedding is not None
    assert len(repository.last_query_embedding) == 384
    assert len(results) == 1
    assert results[0].chunk_id == chunk_id
    assert results[0].document_id == document_id
    assert results[0].patient_id == patient_id
    assert results[0].chunk_index == 2
    assert results[0].content == "Troponin elevation followed chest discomfort."
    assert results[0].embedding_model == "local-hashing-embedding-v1"
    assert results[0].token_count == 5
    assert results[0].chunk_metadata == {"char_start": 100, "char_end": 145}
    assert results[0].created_at == created_at


def test_search_returns_empty_results_for_blank_query() -> None:
    repository = FakeDocumentChunkRepository()

    results = PatientDocumentSimilaritySearchService(
        document_chunks=repository,
        embedding_service=HashingEmbeddingService(),
    ).search(
        patient_id=uuid4(),
        query=" \n ",
    )

    assert results == []
    assert repository.last_query_embedding is None


def test_search_rejects_non_positive_limit() -> None:
    service = PatientDocumentSimilaritySearchService(
        document_chunks=FakeDocumentChunkRepository(),
        embedding_service=HashingEmbeddingService(),
    )

    with pytest.raises(ValueError, match="limit"):
        service.search(patient_id=uuid4(), query="chest pain", limit=0)
