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


def test_graph_writes_are_idempotent_by_using_merge_not_create() -> None:
    session = RecordingSession()
    repository = ClinicalGraphRepository(session)

    repository.upsert_document_node("document-1", {"filename": "note.txt"})
    repository.upsert_chunk_node("chunk-1", {"chunk_index": 0})
    repository.create_relationship(
        from_label="Document",
        from_key="id",
        from_value="document-1",
        relationship_type="DOCUMENT_HAS_CHUNK",
        to_label="Chunk",
        to_key="id",
        to_value="chunk-1",
    )

    queries = [normalize_query(query) for query, _parameters in session.calls]
    assert all("MERGE" in query for query in queries)
    assert all("CREATE " not in query for query in queries)


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


def test_link_chunk_to_entity_uses_mentions_relationship() -> None:
    session = RecordingSession()
    repository = ClinicalGraphRepository(session)

    repository.link_chunk_to_entity(
        chunk_id="chunk-1",
        entity_label="Symptom",
        entity_key="normalized_name",
        entity_value="chest pain",
        properties={"confidence": 0.76},
    )

    query, parameters = session.calls[0]
    normalized_query = normalize_query(query)
    assert "MATCH (source:Chunk {id: $from_value})" in normalized_query
    assert "MATCH (target:Symptom {normalized_name: $to_value})" in normalized_query
    assert "MERGE (source)-[relationship:CHUNK_MENTIONS_ENTITY]->(target)" in normalized_query
    assert parameters["properties"] == {"confidence": 0.76}


def test_repository_allows_controlled_extracted_relationship_types() -> None:
    session = RecordingSession()
    repository = ClinicalGraphRepository(session)

    repository.create_relationship(
        from_label="Medication",
        from_key="normalized_name",
        from_value="metoprolol",
        relationship_type="WORSENED_AFTER",
        to_label="Symptom",
        to_key="normalized_name",
        to_value="shortness of breath",
    )

    query, _parameters = session.calls[0]
    assert "MERGE (source)-[relationship:WORSENED_AFTER]->(target)" in normalize_query(query)


def test_delete_document_subgraph_deletes_document_chunks_and_chunk_scoped_relationships() -> None:
    session = RecordingSession()
    repository = ClinicalGraphRepository(session)

    repository.delete_document_subgraph("document-1")

    query, parameters = session.calls[0]
    normalized_query = normalize_query(query)
    assert "MATCH (document:Document {id: $document_id})" in normalized_query
    assert "OPTIONAL MATCH (document)-[:DOCUMENT_HAS_CHUNK]->(chunk:Chunk)" in normalized_query
    assert "WHERE semantic_relationship.source_chunk_id IN chunk_ids" in normalized_query
    assert "DETACH DELETE chunk" in normalized_query
    assert "DETACH DELETE document" in normalized_query
    assert "Patient" not in normalized_query
    assert parameters == {"document_id": "document-1"}


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
