from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from medgraph_api.api.deps import get_patient_repository, get_upload_storage
from medgraph_api.main import app
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
def client(tmp_path, patient: FakePatient) -> Iterator[TestClient]:
    repository = FakePatientRepository(patient)
    storage = LocalUploadStorage(upload_dir=str(tmp_path / "uploads"))

    def override_patient_repository() -> Iterator[FakePatientRepository]:
        yield repository

    def override_upload_storage() -> LocalUploadStorage:
        return storage

    app.dependency_overrides[get_patient_repository] = override_patient_repository
    app.dependency_overrides[get_upload_storage] = override_upload_storage
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_upload_patient_document(client: TestClient, patient: FakePatient) -> None:
    response = client.post(
        f"/patients/{patient.id}/documents",
        files={"file": ("note.txt", b"Patient reports chest discomfort.", "text/plain")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["patient_id"] == str(patient.id)
    assert body["filename"] == "note.txt"
    assert body["content_type"] == "text/plain"
    assert body["size_bytes"] == 33
    assert body["storage_path"].endswith("note.txt")


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
