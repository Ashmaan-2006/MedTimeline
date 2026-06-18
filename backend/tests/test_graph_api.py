from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from medgraph_api.api.deps import get_clinical_graph_query_service, get_patient_repository
from medgraph_api.main import app
from medgraph_api.services.graph_query_service import (
    EntityPathStep,
    EvidenceChunk,
    GraphEntity,
    GraphRelationship,
    PatientGraphSummary,
)


@dataclass
class FakePatient:
    id: UUID
    created_at: datetime
    updated_at: datetime


class FakePatientRepository:
    def __init__(self, patient: FakePatient | None) -> None:
        self.patient = patient

    def get(self, patient_id: UUID) -> FakePatient | None:
        if self.patient is not None and self.patient.id == patient_id:
            return self.patient
        return None


class FakeGraphQueryService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def get_patient_graph_summary(self, patient_id: str) -> PatientGraphSummary:
        self.calls.append(("summary", (patient_id,)))
        return PatientGraphSummary(
            patient_id=patient_id,
            document_count=2,
            chunk_count=5,
            entity_count=3,
            relationship_count=8,
        )

    def get_entities_for_patient(self, patient_id: str) -> list[GraphEntity]:
        self.calls.append(("entities", (patient_id,)))
        return [
            GraphEntity(
                label="Medication",
                normalized_name="metoprolol",
                name="Metoprolol",
                mention_count=2,
                evidence_count=2,
                latest_seen_at="2026-01-05T00:00:00+00:00",
            )
        ]

    def get_relationships_for_patient(self, patient_id: str) -> list[GraphRelationship]:
        self.calls.append(("relationships", (patient_id,)))
        return [
            GraphRelationship(
                source_label="Medication",
                source_name="metoprolol",
                relationship_type="WORSENED_AFTER",
                target_label="Symptom",
                target_name="shortness of breath",
                evidence="shortness of breath after metoprolol",
                confidence=0.72,
                source_chunk_id="chunk-1",
            )
        ]

    def get_evidence_chunks_for_entity(self, patient_id: str, entity: str) -> list[EvidenceChunk]:
        self.calls.append(("evidence", (patient_id, entity)))
        if not entity.strip():
            raise ValueError("Entity name cannot be blank.")
        return [
            EvidenceChunk(
                chunk_id="chunk-1",
                document_id="document-1",
                chunk_index=0,
                content="Patient reports shortness of breath.",
                evidence="shortness of breath",
                confidence=0.84,
                filename="note.txt",
                created_at="2026-01-05T00:00:00+00:00",
            )
        ]

    def get_paths_between_entities(
        self,
        patient_id: str,
        source: str,
        target: str,
        max_hops: int = 4,
    ) -> list[list[EntityPathStep]]:
        self.calls.append(("path", (patient_id, source, target, max_hops)))
        return [
            [
                EntityPathStep(
                    source={
                        "labels": ["Medication"],
                        "properties": {"normalized_name": source.lower()},
                    },
                    relationship_type="WORSENED_AFTER",
                    relationship={"confidence": 0.72},
                    target={
                        "labels": ["Symptom"],
                        "properties": {"normalized_name": target.lower()},
                    },
                )
            ]
        ]


@pytest.fixture
def patient() -> FakePatient:
    now = datetime.now(UTC)
    return FakePatient(id=uuid4(), created_at=now, updated_at=now)


@pytest.fixture
def graph_query_service() -> FakeGraphQueryService:
    return FakeGraphQueryService()


@pytest.fixture
def client(
    patient: FakePatient,
    graph_query_service: FakeGraphQueryService,
) -> Iterator[TestClient]:
    patient_repository = FakePatientRepository(patient)

    def override_patient_repository() -> Iterator[FakePatientRepository]:
        yield patient_repository

    def override_graph_query_service() -> FakeGraphQueryService:
        return graph_query_service

    app.dependency_overrides[get_patient_repository] = override_patient_repository
    app.dependency_overrides[get_clinical_graph_query_service] = override_graph_query_service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_get_patient_graph_summary(client: TestClient, patient: FakePatient) -> None:
    response = client.get(f"/patients/{patient.id}/graph/summary")

    assert response.status_code == 200
    assert response.json() == {
        "patient_id": str(patient.id),
        "document_count": 2,
        "chunk_count": 5,
        "entity_count": 3,
        "relationship_count": 8,
    }


def test_get_patient_graph_entities(client: TestClient, patient: FakePatient) -> None:
    response = client.get(f"/patients/{patient.id}/graph/entities")

    assert response.status_code == 200
    assert response.json()[0]["normalized_name"] == "metoprolol"


def test_get_patient_graph_relationships(client: TestClient, patient: FakePatient) -> None:
    response = client.get(f"/patients/{patient.id}/graph/relationships")

    assert response.status_code == 200
    assert response.json()[0]["relationship_type"] == "WORSENED_AFTER"
    assert response.json()[0]["target_name"] == "shortness of breath"


def test_get_patient_graph_entity_evidence(client: TestClient, patient: FakePatient) -> None:
    response = client.get(f"/patients/{patient.id}/graph/entity/shortness%20of%20breath/evidence")

    assert response.status_code == 200
    assert response.json()[0]["filename"] == "note.txt"
    assert response.json()[0]["content"] == "Patient reports shortness of breath."


def test_get_patient_graph_path(
    client: TestClient,
    patient: FakePatient,
    graph_query_service: FakeGraphQueryService,
) -> None:
    response = client.get(
        f"/patients/{patient.id}/graph/path",
        params={"source": "Metoprolol", "target": "Shortness of breath", "max_hops": 3},
    )

    assert response.status_code == 200
    assert response.json()[0][0]["relationship_type"] == "WORSENED_AFTER"
    assert graph_query_service.calls[-1] == (
        "path",
        (str(patient.id), "Metoprolol", "Shortness of breath", 3),
    )


def test_graph_endpoints_return_404_for_missing_patient(
    client: TestClient,
    patient: FakePatient,
) -> None:
    missing_patient_id = uuid4()

    response = client.get(f"/patients/{missing_patient_id}/graph/summary")

    assert missing_patient_id != patient.id
    assert response.status_code == 404


def test_graph_path_validates_max_hops(client: TestClient, patient: FakePatient) -> None:
    response = client.get(
        f"/patients/{patient.id}/graph/path",
        params={"source": "metoprolol", "target": "dyspnea", "max_hops": 7},
    )

    assert response.status_code == 422
