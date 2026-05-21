from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from medgraph_api.api.deps import (
    get_document_repository,
    get_patient_repository,
    get_upload_storage,
    get_timeline_event_repository,
)
from medgraph_api.main import app
from medgraph_api.schemas.document import DocumentCreate, DocumentProcessingUpdate
from medgraph_api.schemas.timeline_event import TimelineEventCreate
from medgraph_api.services.storage import LocalUploadStorage


@dataclass
class FakePatient:
    id: UUID
    medical_record_number: str
    first_name: str
    last_name: str
    created_at: datetime
    updated_at: datetime


class FakePatientRepository:
    def __init__(self, patient: FakePatient | None = None) -> None:
        self.patient = patient

    def get(self, patient_id: UUID) -> FakePatient | None:
        if self.patient is not None and self.patient.id == patient_id:
            return self.patient
        return None


@dataclass
class FakeDocument:
    id: UUID
    patient_id: UUID
    filename: str
    content_type: str | None
    storage_path: str
    extracted_text: str | None
    summary: str | None
    created_at: datetime
    updated_at: datetime


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.documents: list[FakeDocument] = []

    def create(self, payload: DocumentCreate) -> FakeDocument:
        now = datetime.now(UTC)
        document = FakeDocument(
            id=uuid4(),
            extracted_text=None,
            summary=None,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        self.documents.append(document)
        return document

    def update_processing(
        self,
        document: FakeDocument,
        payload: DocumentProcessingUpdate,
    ) -> FakeDocument:
        document.extracted_text = payload.extracted_text
        document.summary = payload.summary
        document.updated_at = datetime.now(UTC)
        return document


class FakeTimelineEventRepository:
    def __init__(self) -> None:
        self.events: list[TimelineEventCreate] = []

    def create_many(self, payloads: list[TimelineEventCreate]) -> list[TimelineEventCreate]:
        self.events.extend(payloads)
        return payloads


@pytest.fixture
def patient() -> FakePatient:
    now = datetime.now(UTC)
    return FakePatient(
        id=uuid4(),
        medical_record_number="MRN-UPLOAD-001",
        first_name="Maya",
        last_name="Singh",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def document_repository() -> FakeDocumentRepository:
    return FakeDocumentRepository()


@pytest.fixture
def timeline_event_repository() -> FakeTimelineEventRepository:
    return FakeTimelineEventRepository()


@pytest.fixture
def client(
    tmp_path,
    patient: FakePatient,
    document_repository: FakeDocumentRepository,
    timeline_event_repository: FakeTimelineEventRepository,
) -> Iterator[TestClient]:
    repository = FakePatientRepository(patient)
    storage = LocalUploadStorage(upload_dir=str(tmp_path / "uploads"))

    def override_patient_repository() -> Iterator[FakePatientRepository]:
        yield repository

    def override_upload_storage() -> LocalUploadStorage:
        return storage

    def override_document_repository() -> Iterator[FakeDocumentRepository]:
        yield document_repository

    def override_timeline_event_repository() -> Iterator[FakeTimelineEventRepository]:
        yield timeline_event_repository

    app.dependency_overrides[get_patient_repository] = override_patient_repository
    app.dependency_overrides[get_document_repository] = override_document_repository
    app.dependency_overrides[get_timeline_event_repository] = override_timeline_event_repository
    app.dependency_overrides[get_upload_storage] = override_upload_storage
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_upload_patient_document(
    client: TestClient,
    patient: FakePatient,
    document_repository: FakeDocumentRepository,
    timeline_event_repository: FakeTimelineEventRepository,
) -> None:
    response = client.post(
        f"/patients/{patient.id}/documents",
        files={"file": ("note.txt", b"Patient reports chest discomfort.", "text/plain")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["patient_id"] == str(patient.id)
    assert body["filename"] == "note.txt"
    assert body["content_type"] == "text/plain"
    assert body["storage_path"].endswith("note.txt")
    assert body["extracted_text"] == "Patient reports chest discomfort."
    assert body["summary"] == "Patient reports chest discomfort."
    assert len(document_repository.documents) == 1
    assert document_repository.documents[0].storage_path == body["storage_path"]
    assert document_repository.documents[0].summary == body["summary"]
    assert len(timeline_event_repository.events) == 1
    assert timeline_event_repository.events[0].event_type == "symptom"
    assert timeline_event_repository.events[0].source_document_id == document_repository.documents[0].id


def test_upload_patient_document_returns_404_for_missing_patient(client: TestClient) -> None:
    response = client.post(
        f"/patients/{uuid4()}/documents",
        files={"file": ("note.txt", b"Patient reports chest discomfort.", "text/plain")},
    )

    assert response.status_code == 404


def test_upload_patient_document_requires_filename(client: TestClient, patient: FakePatient) -> None:
    response = client.post(
        f"/patients/{patient.id}/documents",
        files={"file": ("", b"Patient reports chest discomfort.", "text/plain")},
    )

    assert response.status_code == 422
