from datetime import date
from types import SimpleNamespace

import pytest

from medgraph_api.services.graph_query_service import ClinicalGraphQueryService


class FakeResult:
    def __init__(self, records: list[dict]) -> None:
        self.records = records

    def __iter__(self):
        return iter(self.records)

    def single(self):
        if not self.records:
            return None
        return self.records[0]


class RecordingSession:
    def __init__(self, records: list[dict] | None = None) -> None:
        self.records = records or []
        self.calls: list[tuple[str, dict]] = []

    def run(self, query: str, **parameters) -> FakeResult:
        self.calls.append((query, parameters))
        return FakeResult(self.records)


class FakeNode(dict):
    def __init__(self, element_id: str, labels: list[str], properties: dict) -> None:
        super().__init__(properties)
        self.element_id = element_id
        self.labels = labels


class FakeRelationship(dict):
    def __init__(
        self,
        start_node: FakeNode,
        end_node: FakeNode,
        relationship_type: str,
        properties: dict,
    ) -> None:
        super().__init__(properties)
        self.start_node = start_node
        self.end_node = end_node
        self.type = relationship_type


def normalize_query(query: str) -> str:
    return " ".join(query.split())


def test_get_patient_graph_summary_returns_counts() -> None:
    session = RecordingSession(
        [
            {
                "document_count": 2,
                "chunk_count": 6,
                "entity_count": 4,
                "relationship_count": 12,
            }
        ]
    )

    summary = ClinicalGraphQueryService(session).get_patient_graph_summary("patient-1")

    assert summary.patient_id == "patient-1"
    assert summary.document_count == 2
    assert summary.chunk_count == 6
    assert summary.entity_count == 4
    assert summary.relationship_count == 12
    query, parameters = session.calls[0]
    assert "MATCH (patient:Patient {id: $patient_id})" in normalize_query(query)
    assert parameters == {"patient_id": "patient-1"}


def test_get_entities_for_patient_returns_ranked_entities() -> None:
    session = RecordingSession(
        [
            {
                "label": "Medication",
                "normalized_name": "metoprolol",
                "name": "Metoprolol",
                "mention_count": 3,
                "evidence_count": 2,
                "latest_seen_at": "2026-01-05T00:00:00+00:00",
            }
        ]
    )

    entities = ClinicalGraphQueryService(session).get_entities_for_patient("patient-1")

    assert entities[0].label == "Medication"
    assert entities[0].normalized_name == "metoprolol"
    assert entities[0].mention_count == 3
    query, parameters = session.calls[0]
    assert "CHUNK_MENTIONS_ENTITY" in query
    assert parameters == {"patient_id": "patient-1"}


def test_get_events_related_to_medication_normalizes_medication_name() -> None:
    session = RecordingSession(
        [
            {
                "event_id": "event-1",
                "event_type": "medication",
                "title": "Started beta blocker",
                "occurred_at": "2026-01-05",
                "relationship_type": "EVENT_MENTIONS_MEDICATION",
                "confidence": 0.86,
            }
        ]
    )

    events = ClinicalGraphQueryService(session).get_events_related_to_medication(
        patient_id="patient-1",
        medication="  Metoprolol  ",
    )

    assert events[0].event_id == "event-1"
    assert events[0].relationship_type == "EVENT_MENTIONS_MEDICATION"
    assert session.calls[0][1] == {"patient_id": "patient-1", "medication": "metoprolol"}


def test_get_symptoms_near_date_uses_date_range() -> None:
    session = RecordingSession(
        [
            {
                "normalized_name": "shortness of breath",
                "name": "Shortness of breath",
                "chunk_id": "chunk-1",
                "document_id": "document-1",
                "created_at": "2026-01-05T00:00:00+00:00",
                "evidence": "shortness of breath after metoprolol",
                "confidence": 0.72,
            }
        ]
    )

    symptoms = ClinicalGraphQueryService(session).get_symptoms_near_date(
        patient_id="patient-1",
        date_range=(date(2026, 1, 1), date(2026, 1, 31)),
    )

    assert symptoms[0].normalized_name == "shortness of breath"
    assert session.calls[0][1] == {
        "patient_id": "patient-1",
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
    }


def test_get_evidence_chunks_for_entity_returns_citations() -> None:
    session = RecordingSession(
        [
            {
                "chunk_id": "chunk-1",
                "document_id": "document-1",
                "chunk_index": 0,
                "content": "Patient reports chest pain.",
                "evidence": "chest pain",
                "confidence": 0.9,
                "filename": "note.txt",
                "created_at": "2026-01-05T00:00:00+00:00",
            }
        ]
    )

    chunks = ClinicalGraphQueryService(session).get_evidence_chunks_for_entity(
        patient_id="patient-1",
        entity=" Chest Pain ",
    )

    assert chunks[0].content == "Patient reports chest pain."
    assert chunks[0].filename == "note.txt"
    assert session.calls[0][1] == {"patient_id": "patient-1", "entity": "chest pain"}


def test_get_paths_between_entities_serializes_paths() -> None:
    source = FakeNode("node-1", ["Medication"], {"normalized_name": "metoprolol"})
    target = FakeNode("node-2", ["Symptom"], {"normalized_name": "shortness of breath"})
    relationship = FakeRelationship(
        source,
        target,
        "WORSENED_AFTER",
        {"confidence": 0.72},
    )
    path = SimpleNamespace(nodes={"node-1": source, "node-2": target}, relationships=[relationship])
    session = RecordingSession([{"path": path}])

    paths = ClinicalGraphQueryService(session).get_paths_between_entities(
        patient_id="patient-1",
        source="Metoprolol",
        target="Shortness of Breath",
        max_hops=3,
    )

    assert paths[0][0].source["labels"] == ["Medication"]
    assert paths[0][0].target["properties"]["normalized_name"] == "shortness of breath"
    assert paths[0][0].relationship_type == "WORSENED_AFTER"
    query, parameters = session.calls[0]
    assert "*1..3" in query
    assert parameters == {
        "patient_id": "patient-1",
        "source": "metoprolol",
        "target": "shortness of breath",
    }


def test_get_paths_between_entities_rejects_unsafe_hop_counts() -> None:
    with pytest.raises(ValueError, match="max_hops"):
        ClinicalGraphQueryService(RecordingSession()).get_paths_between_entities(
            patient_id="patient-1",
            source="metoprolol",
            target="shortness of breath",
            max_hops=99,
        )


def test_entity_queries_reject_blank_entity_names() -> None:
    with pytest.raises(ValueError, match="blank"):
        ClinicalGraphQueryService(RecordingSession()).get_evidence_chunks_for_entity(
            patient_id="patient-1",
            entity=" ",
        )
