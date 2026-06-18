from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from medgraph_api.services.rag import PatientRagQueryService
from medgraph_api.services.retrieval_filters import RetrievalFilters
from medgraph_api.services.similarity_search import PatientDocumentSearchResult
from medgraph_api.services.graph_query_service import GraphRelationship


@dataclass
class FakeSimilaritySearchService:
    results: list[PatientDocumentSearchResult]
    last_patient_id: UUID | None = None
    last_query: str | None = None
    last_limit: int | None = None
    last_filters: RetrievalFilters | None = None

    def search(
        self,
        patient_id: UUID,
        query: str,
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> list[PatientDocumentSearchResult]:
        self.last_patient_id = patient_id
        self.last_query = query
        self.last_limit = limit
        self.last_filters = filters
        return self.results[:limit]


@dataclass
class FakeGraphQueryService:
    relationships: list[GraphRelationship]
    last_patient_id: str | None = None

    def get_relationships_for_patient(self, patient_id: str) -> list[GraphRelationship]:
        self.last_patient_id = patient_id
        return self.relationships


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
    assert len(result.sources) == 1
    assert result.sources[0].citation_label == "[1]"
    assert result.sources[0].chunk_id == source.chunk_id
    assert result.answer.startswith("Based on the retrieved patient documents:")
    assert "worsening chest pain after medication change [1]." in result.answer
    assert result.graph_evidence == []


def test_rag_service_adds_ordered_citations_for_multiple_sources() -> None:
    patient_id = uuid4()
    now = datetime.now(UTC)
    sources = [
        PatientDocumentSearchResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            patient_id=patient_id,
            chunk_index=0,
            content="Chest pain worsened after a beta blocker dose change.",
            embedding_model="local-hashing-embedding-v1",
            token_count=9,
            chunk_metadata={"char_start": 0, "char_end": 52},
            created_at=now,
        ),
        PatientDocumentSearchResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            patient_id=patient_id,
            chunk_index=1,
            content="Follow-up ECG described new ST depression.",
            embedding_model="local-hashing-embedding-v1",
            token_count=7,
            chunk_metadata={"char_start": 53, "char_end": 95},
            created_at=now,
        ),
    ]

    result = PatientRagQueryService(
        similarity_search=FakeSimilaritySearchService(results=sources),
    ).answer_question(
        patient_id=patient_id,
        question="Why is this patient deteriorating?",
    )

    assert [source.citation_label for source in result.sources] == ["[1]", "[2]"]
    assert "Chest pain worsened after a beta blocker dose change [1]." in result.answer
    assert "Follow-up ECG described new ST depression [2]." in result.answer


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
    assert result.graph_evidence == []


def test_rag_service_passes_retrieval_filters_to_similarity_search() -> None:
    patient_id = uuid4()
    similarity_search = FakeSimilaritySearchService(results=[])
    filters = RetrievalFilters(document_id=uuid4())

    PatientRagQueryService(similarity_search=similarity_search).answer_question(
        patient_id=patient_id,
        question="What changed?",
        filters=filters,
    )

    assert similarity_search.last_filters == filters


def test_rag_service_combines_vector_sources_with_graph_relationships() -> None:
    patient_id = uuid4()
    now = datetime.now(UTC)
    source = PatientDocumentSearchResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        patient_id=patient_id,
        chunk_index=0,
        content="Patient reported shortness of breath after metoprolol change.",
        embedding_model="local-hashing-embedding-v1",
        token_count=8,
        chunk_metadata={"char_start": 0, "char_end": 64},
        created_at=now,
    )
    graph_query = FakeGraphQueryService(
        relationships=[
            GraphRelationship(
                source_label="Medication",
                source_name="metoprolol",
                relationship_type="WORSENED_AFTER",
                target_label="Symptom",
                target_name="shortness of breath",
                evidence="Patient reported shortness of breath after medication change",
                confidence=0.72,
                source_chunk_id=str(source.chunk_id),
            )
        ]
    )

    result = PatientRagQueryService(
        similarity_search=FakeSimilaritySearchService(results=[source]),
        graph_query=graph_query,
    ).answer_question(
        patient_id=patient_id,
        question="Did symptoms worsen after the medication change?",
    )

    assert graph_query.last_patient_id == str(patient_id)
    assert result.answer.startswith("Based on the retrieved patient documents and clinical graph:")
    assert "metoprolol worsened after shortness of breath" in result.answer
    assert result.graph_evidence[0].citation_label == "[G1]"
    assert result.graph_evidence[0].relationship_type == "WORSENED_AFTER"


def test_rag_service_can_answer_from_graph_when_vector_search_has_no_sources() -> None:
    patient_id = uuid4()
    graph_query = FakeGraphQueryService(
        relationships=[
            GraphRelationship(
                source_label="Medication",
                source_name="metoprolol",
                relationship_type="WORSENED_AFTER",
                target_label="Symptom",
                target_name="dyspnea",
                evidence="Dyspnea worsened after metoprolol dose increase",
                confidence=0.69,
                source_chunk_id="chunk-1",
            )
        ]
    )

    result = PatientRagQueryService(
        similarity_search=FakeSimilaritySearchService(results=[]),
        graph_query=graph_query,
    ).answer_question(
        patient_id=patient_id,
        question="Did dyspnea worsen after metoprolol?",
    )

    assert result.sources == []
    assert len(result.graph_evidence) == 1
    assert "clinical graph" in result.answer
