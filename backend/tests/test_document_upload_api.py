from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from medgraph_api.api.deps import (
    get_document_chunk_repository,
    get_document_repository,
    get_patient_repository,
    get_timeline_event_repository,
    get_upload_storage,
)
from medgraph_api.main import app
from medgraph_api.schemas.document import DocumentCreate, DocumentProcessingUpdate
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
    processing_status: str
    processing_error: str | None
    processing_started_at: datetime | None
    processing_completed_at: datetime | None
    celery_task_id: str | None
    processing_attempts: int
    created_at: datetime
    updated_at: datetime


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.documents: list[FakeDocument] = []

    def get(self, document_id: UUID) -> FakeDocument | None:
        for document in self.documents:
            if document.id == document_id:
                return document
        return None

    def create(self, payload: DocumentCreate) -> FakeDocument:
        now = datetime.now(UTC)
        document = FakeDocument(
            id=uuid4(),
            extracted_text=None,
            summary=None,
            processing_error=None,
            processing_started_at=None,
            processing_completed_at=None,
            celery_task_id=None,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        self.documents.append(document)
        return document

    def list_for_patient(
        self,
        patient_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[FakeDocument]:
        matching_documents = [
            document for document in self.documents if document.patient_id == patient_id
        ]
        return matching_documents[skip : skip + limit]

    def update_processing(
        self,
        document: FakeDocument,
        payload: DocumentProcessingUpdate,
    ) -> FakeDocument:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(document, field, value)
        document.updated_at = datetime.now(UTC)
        return document


class FakeDocumentChunkRepository:
    def __init__(self) -> None:
        self.deleted_document_ids: list[UUID] = []

    def delete_for_document(self, document_id: UUID) -> None:
        self.deleted_document_ids.append(document_id)


class FakeTimelineEventRepository:
    def __init__(self) -> None:
        self.deleted_document_ids: list[UUID] = []

    def delete_for_document(self, document_id: UUID) -> None:
        self.deleted_document_ids.append(document_id)


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
def document_chunk_repository() -> FakeDocumentChunkRepository:
    return FakeDocumentChunkRepository()


@pytest.fixture
def timeline_event_repository() -> FakeTimelineEventRepository:
    return FakeTimelineEventRepository()


class FakeAsyncResult:
    id = "task-upload-123"


class FakeProcessDocumentTask:
    def __init__(self) -> None:
        self.document_ids: list[str] = []

    def delay(self, document_id: str) -> FakeAsyncResult:
        self.document_ids.append(document_id)
        return FakeAsyncResult()


@pytest.fixture
def process_document_task() -> FakeProcessDocumentTask:
    return FakeProcessDocumentTask()


@pytest.fixture
def client(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    patient: FakePatient,
    document_repository: FakeDocumentRepository,
    document_chunk_repository: FakeDocumentChunkRepository,
    timeline_event_repository: FakeTimelineEventRepository,
    process_document_task: FakeProcessDocumentTask,
) -> Iterator[TestClient]:
    repository = FakePatientRepository(patient)
    storage = LocalUploadStorage(upload_dir=str(tmp_path / "uploads"))

    def override_patient_repository() -> Iterator[FakePatientRepository]:
        yield repository

    def override_upload_storage() -> LocalUploadStorage:
        return storage

    def override_document_repository() -> Iterator[FakeDocumentRepository]:
        yield document_repository

    def override_document_chunk_repository() -> Iterator[FakeDocumentChunkRepository]:
        yield document_chunk_repository

    def override_timeline_event_repository() -> Iterator[FakeTimelineEventRepository]:
        yield timeline_event_repository

    app.dependency_overrides[get_patient_repository] = override_patient_repository
    app.dependency_overrides[get_document_repository] = override_document_repository
    app.dependency_overrides[get_document_chunk_repository] = override_document_chunk_repository
    app.dependency_overrides[get_timeline_event_repository] = override_timeline_event_repository
    app.dependency_overrides[get_upload_storage] = override_upload_storage
    monkeypatch.setattr(
        "medgraph_api.api.routes.documents.process_document_task",
        process_document_task,
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_upload_patient_document(
    client: TestClient,
    patient: FakePatient,
    document_repository: FakeDocumentRepository,
    process_document_task: FakeProcessDocumentTask,
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
    assert body["extracted_text"] is None
    assert body["summary"] is None
    assert body["processing_status"] == "queued"
    assert body["processing_error"] is None
    assert body["processing_started_at"] is None
    assert body["processing_completed_at"] is None
    assert body["celery_task_id"] == "task-upload-123"
    assert body["processing_attempts"] == 0
    assert len(document_repository.documents) == 1
    assert document_repository.documents[0].storage_path == body["storage_path"]
    assert document_repository.documents[0].summary == body["summary"]
    assert document_repository.documents[0].processing_status == "queued"
    assert document_repository.documents[0].celery_task_id == "task-upload-123"
    assert document_repository.documents[0].processing_attempts == 0
    assert process_document_task.document_ids == [body["id"]]


def test_list_patient_documents(
    client: TestClient,
    patient: FakePatient,
    document_repository: FakeDocumentRepository,
) -> None:
    now = datetime.now(UTC)
    document_repository.documents.append(
        FakeDocument(
            id=uuid4(),
            patient_id=patient.id,
            filename="note.txt",
            content_type="text/plain",
            storage_path="storage/uploads/note.txt",
            extracted_text="Patient reports chest discomfort.",
            summary="Patient reports chest discomfort.",
            processing_status="completed",
            processing_error=None,
            processing_started_at=now,
            processing_completed_at=now,
            celery_task_id=None,
            processing_attempts=1,
            created_at=now,
            updated_at=now,
        )
    )

    response = client.get(f"/patients/{patient.id}/documents")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["filename"] == "note.txt"
    assert body[0]["summary"] == "Patient reports chest discomfort."
    assert body[0]["processing_status"] == "completed"


def test_list_patient_documents_returns_404_for_missing_patient(client: TestClient) -> None:
    response = client.get(f"/patients/{uuid4()}/documents")

    assert response.status_code == 404


def test_get_patient_document_processing_status(
    client: TestClient,
    patient: FakePatient,
    document_repository: FakeDocumentRepository,
) -> None:
    now = datetime.now(UTC)
    document = FakeDocument(
        id=uuid4(),
        patient_id=patient.id,
        filename="note.txt",
        content_type="text/plain",
        storage_path="storage/uploads/note.txt",
        extracted_text=None,
        summary=None,
        processing_status="processing",
        processing_error=None,
        processing_started_at=now,
        processing_completed_at=None,
        celery_task_id="task-upload-123",
        processing_attempts=1,
        created_at=now,
        updated_at=now,
    )
    document_repository.documents.append(document)

    response = client.get(f"/patients/{patient.id}/documents/{document.id}/status")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "document_id": str(document.id),
        "status": "processing",
        "started_at": now.isoformat().replace("+00:00", "Z"),
        "completed_at": None,
        "error": None,
    }


def test_get_patient_document_processing_status_returns_404_for_missing_document(
    client: TestClient,
    patient: FakePatient,
) -> None:
    response = client.get(f"/patients/{patient.id}/documents/{uuid4()}/status")

    assert response.status_code == 404


def test_get_patient_document_processing_status_returns_404_for_other_patient_document(
    client: TestClient,
    patient: FakePatient,
    document_repository: FakeDocumentRepository,
) -> None:
    now = datetime.now(UTC)
    document = FakeDocument(
        id=uuid4(),
        patient_id=uuid4(),
        filename="note.txt",
        content_type="text/plain",
        storage_path="storage/uploads/note.txt",
        extracted_text=None,
        summary=None,
        processing_status="processing",
        processing_error=None,
        processing_started_at=now,
        processing_completed_at=None,
        celery_task_id="task-upload-123",
        processing_attempts=1,
        created_at=now,
        updated_at=now,
    )
    document_repository.documents.append(document)

    response = client.get(f"/patients/{patient.id}/documents/{document.id}/status")

    assert response.status_code == 404


def test_reprocess_patient_document_queues_new_task_and_clears_old_outputs(
    client: TestClient,
    patient: FakePatient,
    document_repository: FakeDocumentRepository,
    document_chunk_repository: FakeDocumentChunkRepository,
    timeline_event_repository: FakeTimelineEventRepository,
    process_document_task: FakeProcessDocumentTask,
) -> None:
    now = datetime.now(UTC)
    document = FakeDocument(
        id=uuid4(),
        patient_id=patient.id,
        filename="note.txt",
        content_type="text/plain",
        storage_path="storage/uploads/note.txt",
        extracted_text="Old extracted text.",
        summary="Old summary.",
        processing_status="failed",
        processing_error="Old failure.",
        processing_started_at=now,
        processing_completed_at=now,
        celery_task_id="old-task-id",
        processing_attempts=2,
        created_at=now,
        updated_at=now,
    )
    document_repository.documents.append(document)

    response = client.post(f"/patients/{patient.id}/documents/{document.id}/reprocess")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(document.id)
    assert body["processing_status"] == "queued"
    assert body["processing_error"] is None
    assert body["processing_started_at"] is None
    assert body["processing_completed_at"] is None
    assert body["celery_task_id"] == "task-upload-123"
    assert body["extracted_text"] is None
    assert body["summary"] is None
    assert body["processing_attempts"] == 2
    assert document_chunk_repository.deleted_document_ids == [document.id]
    assert timeline_event_repository.deleted_document_ids == [document.id]
    assert process_document_task.document_ids == [str(document.id)]


@pytest.mark.parametrize("processing_status", ["queued", "processing"])
def test_reprocess_patient_document_rejects_active_documents(
    client: TestClient,
    patient: FakePatient,
    document_repository: FakeDocumentRepository,
    document_chunk_repository: FakeDocumentChunkRepository,
    timeline_event_repository: FakeTimelineEventRepository,
    process_document_task: FakeProcessDocumentTask,
    processing_status: str,
) -> None:
    now = datetime.now(UTC)
    document = FakeDocument(
        id=uuid4(),
        patient_id=patient.id,
        filename="note.txt",
        content_type="text/plain",
        storage_path="storage/uploads/note.txt",
        extracted_text=None,
        summary=None,
        processing_status=processing_status,
        processing_error=None,
        processing_started_at=now,
        processing_completed_at=None,
        celery_task_id="active-task-id",
        processing_attempts=1,
        created_at=now,
        updated_at=now,
    )
    document_repository.documents.append(document)

    response = client.post(f"/patients/{patient.id}/documents/{document.id}/reprocess")

    assert response.status_code == 409
    assert document_chunk_repository.deleted_document_ids == []
    assert timeline_event_repository.deleted_document_ids == []
    assert process_document_task.document_ids == []


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
