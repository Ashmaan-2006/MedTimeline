from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from medgraph_api.agents.clinical_reasoning_graph import (
    ClinicalReasoningGraphServices,
    create_clinical_reasoning_graph,
    route_after_contradiction_check,
    route_after_retrieval,
    route_retrieval,
)
from medgraph_api.agents.state import create_initial_clinical_agent_state
from medgraph_api.services.graph_query_service import (
    EvidenceChunk,
    GraphEntity,
    GraphRelationship,
)


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
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def search(self, patient_id, query, limit=5, filters=None):
        self.calls.append(
            {
                "patient_id": patient_id,
                "query": query,
                "limit": limit,
                "filters": filters,
            }
        )
        return [
            FakeSearchResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                patient_id=patient_id,
                chunk_index=0,
                content="2026-03-10: Patient reported worsening shortness of breath.",
                embedding_model="test",
                token_count=8,
                chunk_metadata=None,
                created_at=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
                similarity_score=0.9,
            )
        ]


class FakeGraphQueryService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_entities_for_patient(self, patient_id: str):
        self.calls.append("get_entities_for_patient")
        return [
            GraphEntity(
                label="Medication",
                normalized_name="metoprolol",
                name="Metoprolol",
                mention_count=2,
                evidence_count=1,
                latest_seen_at="2026-03-07T00:00:00+00:00",
            )
        ]

    def get_relationships_for_patient(self, patient_id: str):
        self.calls.append("get_relationships_for_patient")
        return [
            GraphRelationship(
                source_label="Symptom",
                source_name="shortness of breath",
                relationship_type="WORSENED_AFTER",
                target_label="Medication",
                target_name="metoprolol",
                evidence="March 10: shortness of breath worsened after metoprolol change",
                confidence=0.8,
                source_chunk_id="chunk-graph",
            )
        ]

    def get_evidence_chunks_for_entity(self, patient_id: str, entity: str):
        self.calls.append("get_evidence_chunks_for_entity")
        return [
            EvidenceChunk(
                chunk_id="chunk-graph",
                document_id="document-graph",
                chunk_index=1,
                content="March 10: shortness of breath worsened after metoprolol change",
                evidence="shortness of breath worsened",
                confidence=0.8,
                filename="note.txt",
                created_at="2026-03-10T00:00:00+00:00",
            )
        ]

    def get_paths_between_entities(self, patient_id: str, source: str, target: str):
        self.calls.append("get_paths_between_entities")
        return []

    def get_events_related_to_medication(self, patient_id: str, medication: str):
        self.calls.append("get_events_related_to_medication")
        return []

    def get_symptoms_near_date(self, patient_id: str, date_range):
        self.calls.append("get_symptoms_near_date")
        return []


def test_clinical_reasoning_graph_runs_hybrid_reasoning_workflow() -> None:
    patient_id = uuid4()
    similarity_search = FakeSimilaritySearchService()
    graph_query = FakeGraphQueryService()
    graph = create_clinical_reasoning_graph(
        ClinicalReasoningGraphServices(
            similarity_search=similarity_search,
            graph_query=graph_query,
            retrieval_limit=3,
        )
    )

    result = graph.invoke(
        create_initial_clinical_agent_state(
            patient_id=str(patient_id),
            user_question="Did symptoms worsen after metoprolol?",
        )
    )

    assert result["intent"] == "symptom_progression"
    assert result["evidence_plan"]["needs_vector_search"] is True
    assert result["evidence_plan"]["needs_graph_search"] is True
    assert similarity_search.calls[0]["limit"] == 3
    assert "get_relationships_for_patient" in graph_query.calls
    assert result["timeline_context"]
    assert result["risk_flags"]
    assert result["final_answer"] is not None
    assert result["citations"]


def test_clinical_reasoning_graph_skips_risk_flagger_for_general_question() -> None:
    graph = create_clinical_reasoning_graph(
        ClinicalReasoningGraphServices(
            similarity_search=FakeSimilaritySearchService(),
            graph_query=FakeGraphQueryService(),
        )
    )

    result = graph.invoke(
        create_initial_clinical_agent_state(
            patient_id=str(uuid4()),
            user_question="Who wrote the note?",
        )
    )

    assert result["intent"] == "general_question"
    assert result["risk_flags"] == []
    assert result["final_answer"] is not None


def test_routing_uses_evidence_plan_and_intent() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Question?")
    state["evidence_plan"] = {
        "needs_vector_search": True,
        "needs_graph_search": True,
        "needs_timeline": True,
    }
    assert route_retrieval(state) == "hybrid"
    assert route_after_retrieval(state) == "timeline_reasoner"

    state["intent"] = "general_question"
    assert route_after_contradiction_check(state) == "answer_generator"

    state["intent"] = "risk_assessment"
    assert route_after_contradiction_check(state) == "risk_flagger"


def test_contradiction_intent_can_route_directly_to_checker_without_timeline() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Any contradictions?")
    state["intent"] = "contradiction_check"
    state["evidence_plan"] = {"needs_timeline": False}

    assert route_after_retrieval(state) == "contradiction_checker"
