from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from medgraph_api.services.clinical_graph_sync import ClinicalGraphSyncService


class RecordingGraphRepository:
    def __init__(self) -> None:
        self.patients: list[tuple[str, dict]] = []
        self.documents: list[tuple[str, dict]] = []
        self.chunks: list[tuple[str, dict]] = []
        self.relationships: list[dict] = []

    def upsert_patient_node(self, patient_id: str, properties: dict) -> None:
        self.patients.append((patient_id, properties))

    def upsert_document_node(self, document_id: str, properties: dict) -> None:
        self.documents.append((document_id, properties))

    def upsert_chunk_node(self, chunk_id: str, properties: dict) -> None:
        self.chunks.append((chunk_id, properties))

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
