from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from medgraph_api.api.deps import get_patient_repository, get_timeline_event_repository
from medgraph_api.main import app
from medgraph_api.schemas.patient import PatientCreate, PatientUpdate


@dataclass
class FakePatient:
    id: UUID
    medical_record_number: str
    first_name: str
    last_name: str
    date_of_birth: date | None
    sex: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class FakePatientRepository:
    def __init__(self) -> None:
        self.patients: dict[UUID, FakePatient] = {}

    def list(self, skip: int = 0, limit: int = 100) -> list[FakePatient]:
        patients = sorted(self.patients.values(), key=lambda patient: patient.created_at, reverse=True)
        return patients[skip : skip + limit]

    def get(self, patient_id: UUID) -> FakePatient | None:
        return self.patients.get(patient_id)

    def get_by_medical_record_number(self, medical_record_number: str) -> FakePatient | None:
        return next(
            (
                patient
                for patient in self.patients.values()
                if patient.medical_record_number == medical_record_number
            ),
            None,
        )

    def create(self, payload: PatientCreate) -> FakePatient:
        now = datetime.now(UTC)
        patient = FakePatient(id=uuid4(), created_at=now, updated_at=now, **payload.model_dump())
        self.patients[patient.id] = patient
        return patient

    def update(self, patient: FakePatient, payload: PatientUpdate) -> FakePatient:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(patient, field, value)
        patient.updated_at = datetime.now(UTC)
        return patient

    def delete(self, patient: FakePatient) -> None:
        self.patients.pop(patient.id, None)


@dataclass
class FakeTimelineEvent:
    id: UUID
    patient_id: UUID
    source_document_id: UUID | None
    occurred_at: datetime | None
    event_type: str
    title: str
    description: str | None
    evidence_text: str | None
    confidence: float | None
    event_metadata: dict | None
    created_at: datetime
    updated_at: datetime


class FakeTimelineEventRepository:
    def __init__(self) -> None:
        self.events: list[FakeTimelineEvent] = []
        self.last_skip: int | None = None
        self.last_limit: int | None = None

    def list_for_patient(
        self,
        patient_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[FakeTimelineEvent]:
        self.last_skip = skip
        self.last_limit = limit
        matching_events = [event for event in self.events if event.patient_id == patient_id]
        return matching_events[skip : skip + limit]


@pytest.fixture
def fake_timeline_event_repository() -> FakeTimelineEventRepository:
    return FakeTimelineEventRepository()


@pytest.fixture
def fake_patient_repository(
    fake_timeline_event_repository: FakeTimelineEventRepository,
) -> Iterator[FakePatientRepository]:
    repository = FakePatientRepository()

    def override_patient_repository() -> Iterator[FakePatientRepository]:
        yield repository

    def override_timeline_event_repository() -> Iterator[FakeTimelineEventRepository]:
        yield fake_timeline_event_repository

    app.dependency_overrides[get_patient_repository] = override_patient_repository
    app.dependency_overrides[get_timeline_event_repository] = override_timeline_event_repository
    try:
        yield repository
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(fake_patient_repository: FakePatientRepository) -> TestClient:
    return TestClient(app)


def test_create_patient(client: TestClient) -> None:
    response = client.post(
        "/patients",
        json={
            "medical_record_number": "MRN-001",
            "first_name": "Maya",
            "last_name": "Singh",
            "date_of_birth": "1978-04-12",
            "sex": "female",
            "notes": "History of palpitations.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["medical_record_number"] == "MRN-001"
    assert body["first_name"] == "Maya"


def test_list_and_get_patient(client: TestClient) -> None:
    created = client.post(
        "/patients",
        json={
            "medical_record_number": "MRN-002",
            "first_name": "Omar",
            "last_name": "Patel",
        },
    ).json()

    list_response = client.get("/patients")
    get_response = client.get(f"/patients/{created['id']}")

    assert list_response.status_code == 200
    assert [patient["id"] for patient in list_response.json()] == [created["id"]]
    assert get_response.status_code == 200
    assert get_response.json()["medical_record_number"] == "MRN-002"


def test_update_patient(client: TestClient) -> None:
    created = client.post(
        "/patients",
        json={
            "medical_record_number": "MRN-003",
            "first_name": "Lena",
            "last_name": "Chen",
        },
    ).json()

    response = client.patch(
        f"/patients/{created['id']}",
        json={"notes": "New exertional dyspnea reported."},
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "New exertional dyspnea reported."


def test_delete_patient(client: TestClient) -> None:
    created = client.post(
        "/patients",
        json={
            "medical_record_number": "MRN-004",
            "first_name": "Noah",
            "last_name": "Brooks",
        },
    ).json()

    delete_response = client.delete(f"/patients/{created['id']}")
    get_response = client.get(f"/patients/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_create_patient_rejects_duplicate_medical_record_number(client: TestClient) -> None:
    payload = {
        "medical_record_number": "MRN-005",
        "first_name": "Ava",
        "last_name": "Morgan",
    }

    first_response = client.post("/patients", json=payload)
    second_response = client.post("/patients", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_get_missing_patient_returns_404(client: TestClient) -> None:
    response = client.get(f"/patients/{uuid4()}")

    assert response.status_code == 404


def test_list_patient_timeline_events(
    client: TestClient,
    fake_timeline_event_repository: FakeTimelineEventRepository,
) -> None:
    created = client.post(
        "/patients",
        json={
            "medical_record_number": "MRN-006",
            "first_name": "Iris",
            "last_name": "Khan",
        },
    ).json()
    patient_id = UUID(created["id"])
    now = datetime.now(UTC)
    fake_timeline_event_repository.events.append(
        FakeTimelineEvent(
            id=uuid4(),
            patient_id=patient_id,
            source_document_id=None,
            occurred_at=now,
            event_type="symptom",
            title="Patient reports chest discomfort.",
            description="Patient reports chest discomfort.",
            evidence_text="Patient reports chest discomfort.",
            confidence=0.65,
            event_metadata={"extractor": "basic_keyword_v1"},
            created_at=now,
            updated_at=now,
        )
    )

    response = client.get(f"/patients/{patient_id}/timeline-events?skip=0&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["event_type"] == "symptom"
    assert body[0]["title"] == "Patient reports chest discomfort."
    assert fake_timeline_event_repository.last_skip == 0
    assert fake_timeline_event_repository.last_limit == 10


def test_list_patient_timeline_events_returns_404_for_missing_patient(client: TestClient) -> None:
    response = client.get(f"/patients/{uuid4()}/timeline-events")

    assert response.status_code == 404
