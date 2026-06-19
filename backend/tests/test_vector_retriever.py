from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from medgraph_api.agents.nodes.vector_retriever import (
    VectorRetrievalNode,
    build_retrieval_filters,
    build_source_snippet,
    build_vector_query,
    retrieve_vector_context_node,
)
from medgraph_api.agents.state import create_initial_clinical_agent_state
from medgraph_api.services.retrieval_filters import RetrievalFilters


@dataclass(frozen=True)
class FakeSearchResult:
    chunk_id: UUID
    document_id: UUID
    patient_id: UUID
    chunk_index: int
    content: str
    embedding_model: str | None
    token_count: int | None
    chunk_metadata: dict | None
    created_at: datetime
    similarity_score: float | None = None


class FakeSimilaritySearchService:
    def __init__(self, results: list[FakeSearchResult] | None = None) -> None:
        self.results = results or []
        self.last_patient_id: UUID | None = None
        self.last_query: str | None = None
        self.last_limit: int | None = None
        self.last_filters: RetrievalFilters | None = None

    def search(
        self,
        patient_id: UUID,
        query: str,
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> list[FakeSearchResult]:
        self.last_patient_id = patient_id
        self.last_query = query
        self.last_limit = limit
        self.last_filters = filters
        return self.results[:limit]


def test_vector_retrieval_node_populates_vector_context_from_similarity_search() -> None:
    patient_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    created_at = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
    service = FakeSimilaritySearchService(
        results=[
            FakeSearchResult(
                chunk_id=chunk_id,
                document_id=document_id,
                patient_id=patient_id,
                chunk_index=3,
                content="Patient reported shortness of breath after metoprolol dose change.",
                embedding_model="local-hashing-embedding-v1",
                token_count=9,
                chunk_metadata={"char_start": 20, "char_end": 84},
                created_at=created_at,
                similarity_score=0.91,
            )
        ]
    )
    state = create_initial_clinical_agent_state(
        patient_id=str(patient_id),
        user_question="Did symptoms worsen?",
    )
    state["evidence_plan"] = {
        "needs_vector_search": True,
        "needs_graph_search": True,
        "needs_timeline": True,
        "target_entities": ["metoprolol", "shortness of breath"],
        "date_range": {"start": "2026-01-01", "end": "2026-01-31"},
        "required_evidence": ["symptoms", "medications", "timeline_events"],
    }

    next_state = retrieve_vector_context_node(state, service, limit=4)

    assert service.last_patient_id == patient_id
    assert service.last_query == "Did symptoms worsen? metoprolol shortness of breath"
    assert service.last_limit == 4
    assert service.last_filters is not None
    assert service.last_filters.created_from == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert service.last_filters.created_to == datetime(
        2026, 1, 31, 23, 59, 59, 999999, tzinfo=UTC
    )
    assert next_state["vector_context"] == [
        {
            "chunk_id": str(chunk_id),
            "document_id": str(document_id),
            "patient_id": str(patient_id),
            "chunk_index": 3,
            "content": "Patient reported shortness of breath after metoprolol dose change.",
            "source_snippet": "Patient reported shortness of breath after metoprolol dose change.",
            "similarity_score": 0.91,
            "embedding_model": "local-hashing-embedding-v1",
            "token_count": 9,
            "chunk_metadata": {"char_start": 20, "char_end": 84},
            "created_at": "2026-01-05T14:30:00+00:00",
        }
    ]


def test_vector_retrieval_node_can_be_used_as_callable_node() -> None:
    patient_id = uuid4()
    service = FakeSimilaritySearchService()
    state = create_initial_clinical_agent_state(str(patient_id), "What happened?")

    next_state = VectorRetrievalNode(service)(state)

    assert service.last_patient_id == patient_id
    assert service.last_query == "What happened?"
    assert next_state["vector_context"] == []


def test_vector_retrieval_node_skips_when_plan_disables_vector_search() -> None:
    service = FakeSimilaritySearchService()
    state = create_initial_clinical_agent_state(str(uuid4()), "What happened?")
    state["evidence_plan"] = {"needs_vector_search": False}
    state["vector_context"] = [{"chunk_id": "old"}]

    next_state = retrieve_vector_context_node(state, service)

    assert service.last_patient_id is None
    assert next_state["vector_context"] == []


def test_vector_retrieval_node_records_safe_error_for_invalid_patient_id() -> None:
    state = create_initial_clinical_agent_state("not-a-uuid", "What happened?")

    next_state = retrieve_vector_context_node(state, FakeSimilaritySearchService())

    assert next_state["errors"] == [
        "Vector retrieval skipped because patient_id is not a valid UUID."
    ]


def test_build_retrieval_filters_returns_none_without_date_range() -> None:
    assert build_retrieval_filters({}) is None


def test_build_vector_query_appends_target_entities() -> None:
    query = build_vector_query("  Did symptoms worsen? ", ["metoprolol", " "])

    assert query == "Did symptoms worsen? metoprolol"


def test_build_source_snippet_truncates_long_content() -> None:
    snippet = build_source_snippet("word " * 100, max_length=25)

    assert snippet == "word word word word..."
    assert len(snippet) <= 25
