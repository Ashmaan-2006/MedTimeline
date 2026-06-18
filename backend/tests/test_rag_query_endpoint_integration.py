from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from medgraph_api.api.deps import (
    get_clinical_graph_query_service,
    get_document_chunk_repository,
    get_patient_repository,
)
from medgraph_api.main import app
from medgraph_api.services.retrieval_filters import RetrievalFilters


@dataclass
class FakePatient:
    id: UUID
    medical_record_number: str
    first_name: str
    last_name: str
    created_at: datetime
    updated_at: datetime


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


class FakePatientRepository:
    def __init__(self, patient: FakePatient | None) -> None:
        self.patient = patient

    def get(self, patient_id: UUID) -> FakePatient | None:
        if self.patient is not None and self.patient.id == patient_id:
            return self.patient
        return None


class FakeDocumentChunkRepository:
    def __init__(self, chunks: list[FakeDocumentChunk]) -> None:
        self.chunks = chunks
        self.last_patient_id: UUID | None = None
        self.last_query_embedding: list[float] | None = None
        self.last_limit: int | None = None
        self.last_filters: RetrievalFilters | None = None

    def search_similar_for_patient(
        self,
        patient_id: UUID,
        query_embedding: list[float],
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> list[FakeDocumentChunk]:
        self.last_patient_id = patient_id
        self.last_query_embedding = query_embedding
        self.last_limit = limit
        self.last_filters = filters

        filtered_chunks = [chunk for chunk in self.chunks if chunk.patient_id == patient_id]
        if filters is not None and filters.document_id is not None:
            filtered_chunks = [
                chunk for chunk in filtered_chunks if chunk.document_id == filters.document_id
            ]
        if filters is not None and filters.created_from is not None:
            filtered_chunks = [
                chunk for chunk in filtered_chunks if chunk.created_at >= filters.created_from
            ]
        if filters is not None and filters.created_to is not None:
            filtered_chunks = [
                chunk for chunk in filtered_chunks if chunk.created_at <= filters.created_to
            ]

        return filtered_chunks[:limit]


class FakeGraphQueryService:
    def get_relationships_for_patient(self, patient_id: str) -> list:
        return []


def make_patient() -> FakePatient:
    now = datetime.now(UTC)
    return FakePatient(
        id=uuid4(),
        medical_record_number="MRN-RAG-INT-001",
        first_name="Maya",
        last_name="Singh",
        created_at=now,
        updated_at=now,
    )


@contextmanager
def client_with_repositories(
    patient: FakePatient | None,
    document_chunks: FakeDocumentChunkRepository,
) -> Iterator[TestClient]:
    def override_patient_repository() -> Iterator[FakePatientRepository]:
        yield FakePatientRepository(patient=patient)

    def override_document_chunk_repository() -> Iterator[FakeDocumentChunkRepository]:
        yield document_chunks

    app.dependency_overrides[get_patient_repository] = override_patient_repository
    app.dependency_overrides[get_document_chunk_repository] = override_document_chunk_repository
    app.dependency_overrides[get_clinical_graph_query_service] = FakeGraphQueryService
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_patient_rag_query_endpoint_returns_cited_answer_from_retrieved_chunks() -> None:
    patient = make_patient()
    document_id = uuid4()
    created_at = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    chunk = FakeDocumentChunk(
        id=uuid4(),
        document_id=document_id,
        patient_id=patient.id,
        chunk_index=0,
        content="Chest pain worsened after medication change. ECG follow-up was ordered.",
        embedding_model="local-hashing-embedding-v1",
        token_count=10,
        chunk_metadata={"char_start": 0, "char_end": 68},
        created_at=created_at,
    )
    document_chunks = FakeDocumentChunkRepository(chunks=[chunk])

    with client_with_repositories(patient=patient, document_chunks=document_chunks) as client:
        response = client.post(
            f"/patients/{patient.id}/rag/query",
            json={
                "question": "Why did symptoms worsen?",
                "limit": 2,
                "document_id": str(document_id),
                "created_from": "2026-01-01T00:00:00Z",
                "created_to": "2026-01-31T23:59:59Z",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] == str(patient.id)
    assert body["question"] == "Why did symptoms worsen?"
    assert "Chest pain worsened after medication change [1]." in body["answer"]
    assert body["sources"] == [
        {
            "citation_label": "[1]",
            "chunk_id": str(chunk.id),
            "document_id": str(document_id),
            "patient_id": str(patient.id),
            "chunk_index": 0,
            "content": chunk.content,
            "embedding_model": "local-hashing-embedding-v1",
            "token_count": 10,
            "chunk_metadata": {"char_start": 0, "char_end": 68},
            "created_at": created_at.isoformat().replace("+00:00", "Z"),
        }
    ]
    assert document_chunks.last_patient_id == patient.id
    assert document_chunks.last_limit == 2
    assert document_chunks.last_query_embedding is not None
    assert len(document_chunks.last_query_embedding) == 384
    assert document_chunks.last_filters is not None
    assert document_chunks.last_filters.document_id == document_id
    assert document_chunks.last_filters.created_from is not None
    assert document_chunks.last_filters.created_to is not None


def test_patient_rag_query_endpoint_returns_no_evidence_answer_when_retrieval_is_empty() -> None:
    patient = make_patient()
    document_chunks = FakeDocumentChunkRepository(chunks=[])

    with client_with_repositories(patient=patient, document_chunks=document_chunks) as client:
        response = client.post(
            f"/patients/{patient.id}/rag/query",
            json={"question": "What changed before deterioration?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "No relevant patient document evidence was found for this question."
    assert body["sources"] == []
    assert document_chunks.last_query_embedding is not None


def test_patient_rag_query_endpoint_rejects_invalid_date_filter_range() -> None:
    patient = make_patient()
    document_chunks = FakeDocumentChunkRepository(chunks=[])

    with client_with_repositories(patient=patient, document_chunks=document_chunks) as client:
        response = client.post(
            f"/patients/{patient.id}/rag/query",
            json={
                "question": "What changed?",
                "created_from": "2026-02-01T00:00:00Z",
                "created_to": "2026-01-01T00:00:00Z",
            },
        )

    assert response.status_code == 422
    assert document_chunks.last_query_embedding is None
