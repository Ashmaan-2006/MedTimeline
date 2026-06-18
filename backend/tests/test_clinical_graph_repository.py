import pytest

from medgraph_api.repositories.clinical_graph_repository import ClinicalGraphRepository


class RecordingSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def run(self, query: str, **parameters) -> None:
        self.calls.append((query, parameters))


def normalize_query(query: str) -> str:
    return " ".join(query.split())


def test_upsert_patient_node_uses_merge_and_sets_properties() -> None:
    session = RecordingSession()
    repository = ClinicalGraphRepository(session)

    repository.upsert_patient_node(
        patient_id="patient-1",
        properties={"medical_record_number": "MRN-001"},
    )

    query, parameters = session.calls[0]
    assert "MERGE (node:Patient {id: $value})" in normalize_query(query)
    assert "SET node += $properties" in normalize_query(query)
    assert parameters == {
        "value": "patient-1",
        "properties": {
            "id": "patient-1",
            "medical_record_number": "MRN-001",
        },
    }


def test_upsert_document_chunk_entity_and_event_nodes() -> None:
    session = RecordingSession()
    repository = ClinicalGraphRepository(session)

    repository.upsert_document_node("document-1", {"filename": "note.txt"})
    repository.upsert_chunk_node("chunk-1", {"chunk_index": 0})
    repository.upsert_clinical_event_node("event-1", {"event_type": "symptom"})
    repository.upsert_entity_node(
        "Medication",
        "normalized_name",
        "metoprolol",
        {"name": "Metoprolol"},
    )

    queries = [normalize_query(query) for query, _parameters in session.calls]
    assert "MERGE (node:Document {id: $value})" in queries[0]
    assert "MERGE (node:Chunk {id: $value})" in queries[1]
    assert "MERGE (node:ClinicalEvent {id: $value})" in queries[2]
    assert "MERGE (node:Medication {normalized_name: $value})" in queries[3]


def test_create_relationship_uses_match_and_merge() -> None:
    session = RecordingSession()
    repository = ClinicalGraphRepository(session)

    repository.create_relationship(
        from_label="Patient",
        from_key="id",
        from_value="patient-1",
        relationship_type="PATIENT_HAS_DOCUMENT",
        to_label="Document",
        to_key="id",
        to_value="document-1",
        properties={"source": "upload"},
    )

    query, parameters = session.calls[0]
    normalized_query = normalize_query(query)
    assert "MATCH (source:Patient {id: $from_value})" in normalized_query
    assert "MATCH (target:Document {id: $to_value})" in normalized_query
    assert "MERGE (source)-[relationship:PATIENT_HAS_DOCUMENT]->(target)" in normalized_query
    assert "SET relationship += $properties" in normalized_query
    assert parameters == {
        "from_value": "patient-1",
        "to_value": "document-1",
        "properties": {"source": "upload"},
    }


def test_link_entity_to_chunk_uses_evidence_relationship() -> None:
    session = RecordingSession()
    repository = ClinicalGraphRepository(session)

    repository.link_entity_to_chunk(
        entity_label="Diagnosis",
        entity_key="normalized_name",
        entity_value="heart failure",
        chunk_id="chunk-1",
        properties={"confidence": 0.81},
    )

    query, parameters = session.calls[0]
    normalized_query = normalize_query(query)
    assert "MATCH (source:Diagnosis {normalized_name: $from_value})" in normalized_query
    assert "MATCH (target:Chunk {id: $to_value})" in normalized_query
    assert "MERGE (source)-[relationship:ENTITY_EVIDENCED_BY_CHUNK]->(target)" in normalized_query
    assert parameters["properties"] == {"confidence": 0.81}


def test_link_event_to_patient_uses_patient_event_relationship() -> None:
    session = RecordingSession()
    repository = ClinicalGraphRepository(session)

    repository.link_event_to_patient(patient_id="patient-1", event_id="event-1")

    query, parameters = session.calls[0]
    normalized_query = normalize_query(query)
    assert "MATCH (source:Patient {id: $from_value})" in normalized_query
    assert "MATCH (target:ClinicalEvent {id: $to_value})" in normalized_query
    assert "MERGE (source)-[relationship:PATIENT_HAS_EVENT]->(target)" in normalized_query
    assert parameters["properties"] == {}


def test_repository_rejects_unknown_labels_and_relationships() -> None:
    repository = ClinicalGraphRepository(RecordingSession())

    with pytest.raises(ValueError):
        repository.upsert_entity_node("Unknown", "name", "x", {})

    with pytest.raises(ValueError):
        repository.create_relationship(
            from_label="Patient",
            from_key="id",
            from_value="patient-1",
            relationship_type="UNKNOWN_RELATIONSHIP",
            to_label="Document",
            to_key="id",
            to_value="document-1",
        )
