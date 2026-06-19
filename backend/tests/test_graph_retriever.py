from medgraph_api.agents.nodes.graph_retriever import (
    GraphRetrievalNode,
    filter_relationships,
    normalize_target_entities,
    parse_graph_date_range,
    retrieve_graph_context_node,
)
from medgraph_api.agents.state import create_initial_clinical_agent_state
from medgraph_api.services.graph_query_service import (
    EntityPathStep,
    EvidenceChunk,
    GraphEntity,
    GraphRelationship,
    MedicationRelatedEvent,
    SymptomNearDate,
)


class FakeGraphQueryService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.entities = [
            GraphEntity(
                label="Medication",
                normalized_name="metoprolol",
                name="Metoprolol",
                mention_count=3,
                evidence_count=2,
                latest_seen_at="2026-05-12T00:00:00+00:00",
            ),
            GraphEntity(
                label="Symptom",
                normalized_name="shortness of breath",
                name="Shortness of breath",
                mention_count=2,
                evidence_count=2,
                latest_seen_at="2026-05-18T00:00:00+00:00",
            ),
        ]
        self.relationships = [
            GraphRelationship(
                source_label="Medication",
                source_name="metoprolol",
                relationship_type="STARTED_AT",
                target_label="ClinicalEvent",
                target_name="may 12 event",
                evidence="metoprolol started at May 12 visit",
                confidence=0.88,
                source_chunk_id="chunk-1",
            ),
            GraphRelationship(
                source_label="Symptom",
                source_name="shortness of breath",
                relationship_type="WORSENED_AFTER",
                target_label="ClinicalEvent",
                target_name="may 18 event",
                evidence="shortness of breath worsened on May 18",
                confidence=0.8,
                source_chunk_id="chunk-2",
            ),
        ]

    def get_entities_for_patient(self, patient_id: str):
        self.calls.append(("get_entities_for_patient", (patient_id,)))
        return self.entities

    def get_relationships_for_patient(self, patient_id: str):
        self.calls.append(("get_relationships_for_patient", (patient_id,)))
        return self.relationships

    def get_evidence_chunks_for_entity(self, patient_id: str, entity: str):
        self.calls.append(("get_evidence_chunks_for_entity", (patient_id, entity)))
        return [
            EvidenceChunk(
                chunk_id=f"chunk-{entity}",
                document_id="document-1",
                chunk_index=1,
                content=f"Evidence for {entity}.",
                evidence=entity,
                confidence=0.91,
                filename="note.txt",
                created_at="2026-05-12T00:00:00+00:00",
            )
        ]

    def get_paths_between_entities(self, patient_id: str, source: str, target: str):
        self.calls.append(("get_paths_between_entities", (patient_id, source, target)))
        return [
            [
                EntityPathStep(
                    source={"labels": ["Medication"], "properties": {"normalized_name": source}},
                    relationship_type="WORSENED_AFTER",
                    relationship={"confidence": 0.77},
                    target={"labels": ["Symptom"], "properties": {"normalized_name": target}},
                )
            ]
        ]

    def get_events_related_to_medication(self, patient_id: str, medication: str):
        self.calls.append(("get_events_related_to_medication", (patient_id, medication)))
        return [
            MedicationRelatedEvent(
                event_id=f"event-{medication}",
                event_type="medication",
                title=f"{medication} started",
                occurred_at="2026-05-12",
                relationship_type="STARTED_AT",
                confidence=0.84,
            )
        ]

    def get_symptoms_near_date(self, patient_id: str, date_range):
        self.calls.append(("get_symptoms_near_date", (patient_id, date_range)))
        return [
            SymptomNearDate(
                normalized_name="shortness of breath",
                name="Shortness of breath",
                chunk_id="chunk-2",
                document_id="document-1",
                created_at="2026-05-18T00:00:00+00:00",
                evidence="worse shortness of breath",
                confidence=0.8,
            )
        ]


def test_graph_retrieval_node_populates_relationship_evidence() -> None:
    service = FakeGraphQueryService()
    state = create_initial_clinical_agent_state(
        patient_id="patient-1",
        user_question="Did symptoms worsen after metoprolol?",
    )
    state["evidence_plan"] = {
        "needs_vector_search": True,
        "needs_graph_search": True,
        "needs_timeline": True,
        "target_entities": ["Metoprolol", "shortness of breath"],
        "date_range": {"start": "2026-05-01", "end": "2026-05-31"},
        "required_evidence": ["symptoms", "medications", "timeline_events"],
    }

    next_state = retrieve_graph_context_node(state, service, limit=5)

    assert [section["type"] for section in next_state["graph_context"]] == [
        "entities",
        "relationships",
        "entity_evidence_chunks",
        "entity_paths",
        "entity_connected_events",
        "symptoms_near_date",
    ]
    assert next_state["graph_context"][1]["items"] == [
        {
            "source_label": "Medication",
            "source_name": "metoprolol",
            "relationship_type": "STARTED_AT",
            "target_label": "ClinicalEvent",
            "target_name": "may 12 event",
            "evidence": "metoprolol started at May 12 visit",
            "confidence": 0.88,
            "source_chunk_id": "chunk-1",
        },
        {
            "source_label": "Symptom",
            "source_name": "shortness of breath",
            "relationship_type": "WORSENED_AFTER",
            "target_label": "ClinicalEvent",
            "target_name": "may 18 event",
            "evidence": "shortness of breath worsened on May 18",
            "confidence": 0.8,
            "source_chunk_id": "chunk-2",
        },
    ]
    assert ("get_paths_between_entities", ("patient-1", "metoprolol", "shortness of breath")) in (
        service.calls
    )
    assert service.calls[-1] == (
        "get_symptoms_near_date",
        ("patient-1", parse_graph_date_range({"start": "2026-05-01", "end": "2026-05-31"})),
    )


def test_graph_retrieval_node_can_be_used_as_callable_node() -> None:
    service = FakeGraphQueryService()
    state = create_initial_clinical_agent_state("patient-1", "What graph evidence exists?")

    next_state = GraphRetrievalNode(service, limit=1)(state)

    assert next_state["graph_context"][0]["type"] == "entities"
    assert len(next_state["graph_context"][0]["items"]) == 1


def test_graph_retrieval_node_skips_when_plan_disables_graph_search() -> None:
    service = FakeGraphQueryService()
    state = create_initial_clinical_agent_state("patient-1", "What happened?")
    state["evidence_plan"] = {"needs_graph_search": False}
    state["graph_context"] = [{"type": "old"}]

    next_state = retrieve_graph_context_node(state, service)

    assert next_state["graph_context"] == []
    assert service.calls == []


def test_graph_retrieval_node_records_safe_error_for_missing_patient_id() -> None:
    state = create_initial_clinical_agent_state("", "What happened?")

    next_state = retrieve_graph_context_node(state, FakeGraphQueryService())

    assert next_state["errors"] == ["Graph retrieval skipped because patient_id is missing."]


def test_normalize_target_entities_deduplicates_values() -> None:
    assert normalize_target_entities([" Metoprolol ", "metoprolol", "", "Shortness  of breath"]) == [
        "metoprolol",
        "shortness of breath",
    ]


def test_filter_relationships_returns_target_entity_matches() -> None:
    relationships = [
        GraphRelationship(
            source_label="Medication",
            source_name="metoprolol",
            relationship_type="STARTED_AT",
            target_label="ClinicalEvent",
            target_name="may 12 event",
            evidence=None,
            confidence=None,
            source_chunk_id=None,
        ),
        GraphRelationship(
            source_label="Diagnosis",
            source_name="atrial fibrillation",
            relationship_type="SUPPORTS",
            target_label="Finding",
            target_name="ecg finding",
            evidence=None,
            confidence=None,
            source_chunk_id=None,
        ),
    ]

    assert filter_relationships(relationships, ["metoprolol"]) == [relationships[0]]


def test_parse_graph_date_range_from_iso_dates() -> None:
    date_range = parse_graph_date_range({"start": "2026-05-01", "end": "2026-05-31"})

    assert date_range is not None
    assert date_range[0].isoformat() == "2026-05-01"
    assert date_range[1].isoformat() == "2026-05-31"
