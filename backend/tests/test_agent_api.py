from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from medgraph_api.api.deps import get_clinical_reasoning_graph, get_patient_repository
from medgraph_api.main import app


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


class FakeClinicalReasoningGraph:
    def __init__(self) -> None:
        self.last_state: dict | None = None

    def invoke(self, state: dict) -> dict:
        self.last_state = state
        return {
            **state,
            "intent": "symptom_progression",
            "timeline_context": [
                {
                    "display_date": "March 10",
                    "summary": "Patient reported worsening shortness of breath.",
                    "chunk_id": "chunk-1",
                }
            ],
            "contradictions": [
                {
                    "claim_a": "Patient denied chest pain",
                    "claim_b": "Patient reported chest pain",
                    "evidence_a": "chunk-a",
                    "evidence_b": "chunk-b",
                    "severity": "medium",
                }
            ],
            "risk_flags": [
                {
                    "category": "worsening_symptoms",
                    "title": "Worsening symptom signal",
                    "evidence_ids": ["chunk-1"],
                }
            ],
            "citations": [
                {
                    "label": "[1]",
                    "source_type": "timeline_event",
                    "evidence_id": "chunk-1",
                    "snippet": "Patient reported worsening shortness of breath.",
                }
            ],
            "final_answer": "Timeline evidence suggests worsening symptoms [1].",
            "answer_confidence": "medium",
            "limitations": ["No lab report evidence was available in the retrieved context."],
        }


def test_agent_query_endpoint_returns_langgraph_result() -> None:
    now = datetime.now(UTC)
    patient = FakePatient(id=uuid4(), created_at=now, updated_at=now)
    graph = FakeClinicalReasoningGraph()

    def override_patient_repository() -> Iterator[FakePatientRepository]:
        yield FakePatientRepository(patient=patient)

    def override_clinical_reasoning_graph() -> FakeClinicalReasoningGraph:
        return graph

    app.dependency_overrides[get_patient_repository] = override_patient_repository
    app.dependency_overrides[get_clinical_reasoning_graph] = override_clinical_reasoning_graph
    try:
        response = TestClient(app).post(
            f"/patients/{patient.id}/agent/query",
            json={"question": "Did symptoms worsen after the medication change?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Timeline evidence suggests worsening symptoms [1]."
    assert body["intent"] == "symptom_progression"
    assert body["timeline"][0]["display_date"] == "March 10"
    assert body["contradictions"][0]["severity"] == "medium"
    assert body["risk_flags"][0]["category"] == "worsening_symptoms"
    assert body["citations"][0]["label"] == "[1]"
    assert body["confidence"] == "medium"
    assert body["limitations"] == ["No lab report evidence was available in the retrieved context."]
    assert graph.last_state is not None
    assert graph.last_state["patient_id"] == str(patient.id)
    assert graph.last_state["user_question"] == "Did symptoms worsen after the medication change?"


def test_agent_query_endpoint_returns_404_for_missing_patient() -> None:
    def override_patient_repository() -> Iterator[FakePatientRepository]:
        yield FakePatientRepository(patient=None)

    app.dependency_overrides[get_patient_repository] = override_patient_repository
    try:
        response = TestClient(app).post(
            f"/patients/{uuid4()}/agent/query",
            json={"question": "What happened?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
