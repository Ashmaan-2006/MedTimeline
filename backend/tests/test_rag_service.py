from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from medgraph_api.services.rag import PatientRagQueryService
from medgraph_api.services.similarity_search import PatientDocumentSearchResult


@dataclass
class FakeSimilaritySearchService:
    results: list[PatientDocumentSearchResult]
    last_patient_id: UUID | None = None
    last_query: str | None = None
    last_limit: int | None = None

    def search(
        self,
        patient_id: UUID,
        query: str,
        limit: int = 5,
    ) -> list[PatientDocumentSearchResult]:
        self.last_patient_id = patient_id
        self.last_query = query
        self.last_limit = limit
        return self.results[:limit]


def test_rag_service_returns_grounded_answer_with_sources() -> None:
    patient_id = uuid4()
    source = PatientDocumentSearchResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        patient_id=patient_id,
        chunk_index=0,
        content="Patient reported worsening chest pain after medication change. ECG was abnormal.",
        embedding_model="local-hashing-embedding-v1",
        token_count=10,
        chunk_metadata={"char_start": 0, "char_end": 72},
        created_at=datetime.now(UTC),
    )
    similarity_search = FakeSimilaritySearchService(results=[source])

    result = PatientRagQueryService(similarity_search=similarity_search).answer_question(
        patient_id=patient_id,
        question="  Why did symptoms worsen?  ",
        limit=3,
    )

    assert similarity_search.last_patient_id == patient_id
    assert similarity_search.last_query == "Why did symptoms worsen?"
    assert similarity_search.last_limit == 3
    assert result.patient_id == patient_id
    assert result.question == "Why did symptoms worsen?"
    assert result.sources == [source]
    assert result.answer.startswith("Based on the retrieved patient documents:")
    assert "worsening chest pain" in result.answer


def test_rag_service_returns_no_evidence_answer_without_sources() -> None:
    patient_id = uuid4()

    result = PatientRagQueryService(
        similarity_search=FakeSimilaritySearchService(results=[]),
    ).answer_question(
        patient_id=patient_id,
        question="What changed?",
    )

    assert result.patient_id == patient_id
    assert result.answer == "No relevant patient document evidence was found for this question."
    assert result.sources == []
