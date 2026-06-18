from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from medgraph_api.schemas.clinical_entity import (
    ExtractedClinicalEntities,
    ExtractedClinicalEntity,
)
from medgraph_api.schemas.clinical_relationship import (
    ExtractedClinicalRelationship,
    ExtractedClinicalRelationships,
)
from medgraph_api.services.clinical_graph_sync import ClinicalGraphSyncService


class RecordingGraphRepository:
    def __init__(self) -> None:
        self.patients: list[tuple[str, dict]] = []
        self.documents: list[tuple[str, dict]] = []
        self.chunks: list[tuple[str, dict]] = []
        self.entities: list[tuple[str, str, str, dict]] = []
        self.relationships: list[dict] = []

    def upsert_patient_node(self, patient_id: str, properties: dict) -> None:
        self.patients.append((patient_id, properties))

    def upsert_document_node(self, document_id: str, properties: dict) -> None:
        self.documents.append((document_id, properties))

    def upsert_chunk_node(self, chunk_id: str, properties: dict) -> None:
        self.chunks.append((chunk_id, properties))

    def upsert_entity_node(self, label: str, key: str, value: str, properties: dict) -> None:
        self.entities.append((label, key, value, properties))

    def link_chunk_to_entity(self, **kwargs) -> None:
        self.relationships.append({"helper": "link_chunk_to_entity", **kwargs})

    def link_entity_to_chunk(self, **kwargs) -> None:
        self.relationships.append({"helper": "link_entity_to_chunk", **kwargs})

    def create_relationship(self, **kwargs) -> None:
        self.relationships.append(kwargs)


def test_sync_patient_upserts_patient_node_with_postgres_identity() -> None:
    graph = RecordingGraphRepository()
    patient_id = uuid4()
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    patient = SimpleNamespace(
        id=patient_id,
        medical_record_number="MRN-001",
        first_name="Maya",
        last_name="Singh",
        date_of_birth=date(1978, 4, 12),
        sex="female",
        created_at=created_at,
        updated_at=created_at,
    )

    ClinicalGraphSyncService(graph).sync_patient(patient)

    assert graph.patients == [
        (
            str(patient_id),
            {
                "id": str(patient_id),
                "patient_id": str(patient_id),
                "source_table": "patients",
                "medical_record_number": "MRN-001",
                "first_name": "Maya",
                "last_name": "Singh",
                "date_of_birth": "1978-04-12",
                "sex": "female",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
        )
    ]


def test_sync_document_upserts_document_node_and_patient_relationship() -> None:
    graph = RecordingGraphRepository()
    patient_id = uuid4()
    document_id = uuid4()
    created_at = datetime(2026, 1, 2, tzinfo=UTC)
    document = SimpleNamespace(
        id=document_id,
        patient_id=patient_id,
        filename="note.txt",
        content_type="text/plain",
        processing_status="completed",
        summary="Summary",
        created_at=created_at,
        updated_at=created_at,
    )

    ClinicalGraphSyncService(graph).sync_document(document)

    assert graph.documents[0][0] == str(document_id)
    assert graph.documents[0][1]["document_id"] == str(document_id)
    assert graph.documents[0][1]["patient_id"] == str(patient_id)
    assert graph.documents[0][1]["source_table"] == "documents"
    assert graph.relationships == [
        {
            "from_label": "Patient",
            "from_key": "id",
            "from_value": str(patient_id),
            "relationship_type": "PATIENT_HAS_DOCUMENT",
            "to_label": "Document",
            "to_key": "id",
            "to_value": str(document_id),
        }
    ]


def test_sync_chunk_upserts_chunk_node_and_document_relationship() -> None:
    graph = RecordingGraphRepository()
    patient_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    created_at = datetime(2026, 1, 3, tzinfo=UTC)
    chunk = SimpleNamespace(
        id=chunk_id,
        patient_id=patient_id,
        document_id=document_id,
        chunk_index=2,
        content="Patient reports chest discomfort.",
        embedding_model="local",
        token_count=4,
        chunk_metadata={"char_start": 10, "char_end": 43},
        created_at=created_at,
    )

    ClinicalGraphSyncService(graph).sync_chunk(chunk)

    assert graph.chunks[0][0] == str(chunk_id)
    assert graph.chunks[0][1]["chunk_id"] == str(chunk_id)
    assert graph.chunks[0][1]["document_id"] == str(document_id)
    assert graph.chunks[0][1]["patient_id"] == str(patient_id)
    assert graph.chunks[0][1]["source_table"] == "document_chunks"
    assert graph.chunks[0][1]["char_start"] == 10
    assert graph.relationships == [
        {
            "from_label": "Document",
            "from_key": "id",
            "from_value": str(document_id),
            "relationship_type": "DOCUMENT_HAS_CHUNK",
            "to_label": "Chunk",
            "to_key": "id",
            "to_value": str(chunk_id),
        }
    ]


def test_sync_entities_for_chunk_upserts_entities_and_links_to_chunk() -> None:
    graph = RecordingGraphRepository()
    patient_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    created_at = datetime(2026, 1, 4, tzinfo=UTC)
    chunk = SimpleNamespace(
        id=chunk_id,
        patient_id=patient_id,
        document_id=document_id,
        chunk_index=0,
        content="Patient reports shortness of breath after metoprolol.",
        embedding_model="local",
        token_count=7,
        chunk_metadata={},
        created_at=created_at,
    )
    entities = ExtractedClinicalEntities(
        entities=[
            ExtractedClinicalEntity(
                entity_type="symptom",
                name="shortness of breath",
                normalized_name="shortness of breath",
                source_chunk_id=chunk_id,
                confidence=0.82,
                evidence_quote="shortness of breath after metoprolol",
            )
        ]
    )

    ClinicalGraphSyncService(graph).sync_entities_for_chunk(chunk, entities)

    assert graph.entities[0][0] == "Symptom"
    assert graph.entities[0][1] == "normalized_name"
    assert graph.entities[0][2] == "shortness of breath"
    assert graph.entities[0][3]["patient_id"] == str(patient_id)
    assert graph.entities[0][3]["source_chunk_id"] == str(chunk_id)
    assert graph.relationships[0]["helper"] == "link_chunk_to_entity"
    assert graph.relationships[1]["helper"] == "link_entity_to_chunk"


def test_sync_relationships_writes_controlled_entity_relationships() -> None:
    graph = RecordingGraphRepository()
    chunk_id = uuid4()
    entities = ExtractedClinicalEntities(
        entities=[
            ExtractedClinicalEntity(
                entity_type="medication",
                name="metoprolol",
                normalized_name="metoprolol",
                source_chunk_id=chunk_id,
                confidence=0.9,
                evidence_quote="metoprolol",
            ),
            ExtractedClinicalEntity(
                entity_type="symptom",
                name="shortness of breath",
                normalized_name="shortness of breath",
                source_chunk_id=chunk_id,
                confidence=0.8,
                evidence_quote="shortness of breath",
            ),
        ]
    )
    relationships = ExtractedClinicalRelationships(
        relationships=[
            ExtractedClinicalRelationship(
                source="metoprolol",
                target="shortness of breath",
                type="WORSENED_AFTER",
                source_chunk_id=chunk_id,
                evidence="shortness of breath after metoprolol",
                confidence=0.72,
            )
        ]
    )

    ClinicalGraphSyncService(graph).sync_relationships(entities, relationships)

    assert graph.relationships == [
        {
            "from_label": "Medication",
            "from_key": "normalized_name",
            "from_value": "metoprolol",
            "relationship_type": "WORSENED_AFTER",
            "to_label": "Symptom",
            "to_key": "normalized_name",
            "to_value": "shortness of breath",
            "properties": {
                "source_chunk_id": str(chunk_id),
                "evidence": "shortness of breath after metoprolol",
                "confidence": 0.72,
            },
        }
    ]
