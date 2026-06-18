from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from medgraph_api.api.deps import get_patient_rag_query_service, get_patient_repository
from medgraph_api.main import app
from medgraph_api.services.rag import (
    PatientRagCitationSource,
    PatientRagGraphEvidence,
    PatientRagQueryResult,
)
from medgraph_api.services.retrieval_filters import RetrievalFilters
from medgraph_api.services.similarity_search import PatientDocumentSearchResult


@dataclass
class FakePatient:
    id: UUID
    medical_record_number: str
    first_name: str
    last_name: str
    created_at: datetime
    updated_at: datetime


class FakePatientRepository:
    def __init__(self, patient: FakePatient | None = None) -> None:
        self.patient = patient

    def get(self, patient_id: UUID) -> FakePatient | None:
        if self.patient is not None and self.patient.id == patient_id:
            return self.patient
        return None


class FakeRagQueryService:
    def __init__(self, source: PatientDocumentSearchResult) -> None:
        self.source = source
        self.last_patient_id: UUID | None = None
        self.last_question: str | None = None
        self.last_limit: int | None = None
        self.last_filters: RetrievalFilters | None = None

    def answer_question(
        self,
        patient_id: UUID,
        question: str,
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> PatientRagQueryResult:
        self.last_patient_id = patient_id
        self.last_question = question
        self.last_limit = limit
        self.last_filters = filters
        return PatientRagQueryResult(
            patient_id=patient_id,
            question=question,
            answer="Based on the retrieved patient documents: Chest pain worsened [1].",
            sources=[
                PatientRagCitationSource(
                    citation_label="[1]",
                    chunk_id=self.source.chunk_id,
                    document_id=self.source.document_id,
                    patient_id=self.source.patient_id,
                    chunk_index=self.source.chunk_index,
                    content=self.source.content,
                    embedding_model=self.source.embedding_model,
                    token_count=self.source.token_count,
                    chunk_metadata=self.source.chunk_metadata,
                    created_at=self.source.created_at,
                )
            ],
            graph_evidence=[
                PatientRagGraphEvidence(
                    citation_label="[G1]",
                    source_label="Medication",
                    source_name="metoprolol",
                    relationship_type="WORSENED_AFTER",
                    target_label="Symptom",
                    target_name="chest pain",
                    evidence="Chest pain worsened after medication change.",
                    confidence=0.72,
                    source_chunk_id=str(self.source.chunk_id),
                )
            ],
        )


def test_query_patient_documents_returns_answer_and_sources() -> None:
    now = datetime.now(UTC)
    patient = FakePatient(
        id=uuid4(),
        medical_record_number="MRN-RAG-001",
        first_name="Maya",
        last_name="Singh",
        created_at=now,
        updated_at=now,
    )
    source = PatientDocumentSearchResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        patient_id=patient.id,
        chunk_index=1,
        content="Chest pain worsened after medication change.",
        embedding_model="local-hashing-embedding-v1",
        token_count=6,
        chunk_metadata={"char_start": 12, "char_end": 53},
        created_at=now,
    )
    rag_query_service = FakeRagQueryService(source=source)

    def override_patient_repository() -> Iterator[FakePatientRepository]:
        yield FakePatientRepository(patient=patient)

    def override_rag_query_service() -> FakeRagQueryService:
        return rag_query_service

    app.dependency_overrides[get_patient_repository] = override_patient_repository
    app.dependency_overrides[get_patient_rag_query_service] = override_rag_query_service
    try:
        response = TestClient(app).post(
            f"/patients/{patient.id}/rag/query",
            json={
                "question": "Why did symptoms worsen?",
                "limit": 3,
                "document_id": str(source.document_id),
                "created_from": "2026-01-01T00:00:00Z",
                "created_to": "2026-01-31T23:59:00Z",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] == str(patient.id)
    assert body["question"] == "Why did symptoms worsen?"
    assert body["answer"] == "Based on the retrieved patient documents: Chest pain worsened [1]."
    assert len(body["sources"]) == 1
    assert body["sources"][0]["citation_label"] == "[1]"
    assert body["sources"][0]["chunk_id"] == str(source.chunk_id)
    assert body["sources"][0]["document_id"] == str(source.document_id)
    assert body["sources"][0]["patient_id"] == str(patient.id)
    assert body["sources"][0]["chunk_index"] == 1
    assert body["sources"][0]["content"] == "Chest pain worsened after medication change."
    assert body["graph_evidence"][0]["citation_label"] == "[G1]"
    assert body["graph_evidence"][0]["relationship_type"] == "WORSENED_AFTER"
    assert rag_query_service.last_patient_id == patient.id
    assert rag_query_service.last_question == "Why did symptoms worsen?"
    assert rag_query_service.last_limit == 3
    assert rag_query_service.last_filters is not None
    assert rag_query_service.last_filters.document_id == source.document_id
    assert rag_query_service.last_filters.created_from is not None
    assert rag_query_service.last_filters.created_to is not None


def test_query_patient_documents_returns_404_for_missing_patient() -> None:
    def override_patient_repository() -> Iterator[FakePatientRepository]:
        yield FakePatientRepository(patient=None)

    app.dependency_overrides[get_patient_repository] = override_patient_repository
    try:
        response = TestClient(app).post(
            f"/patients/{uuid4()}/rag/query",
            json={"question": "What happened?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
