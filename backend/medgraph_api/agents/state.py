from typing import Any, TypedDict


class ClinicalAgentState(TypedDict):
    patient_id: str
    user_question: str
    intent: str | None
    evidence_plan: dict[str, Any] | None
    required_evidence: list[str]
    vector_context: list[dict[str, Any]]
    graph_context: list[dict[str, Any]]
    timeline_context: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    risk_flags: list[dict[str, Any]]
    final_answer: str | None
    citations: list[dict[str, Any]]
    errors: list[str]


def create_initial_clinical_agent_state(
    patient_id: str,
    user_question: str,
) -> ClinicalAgentState:
    return ClinicalAgentState(
        patient_id=patient_id,
        user_question=user_question,
        intent=None,
        evidence_plan=None,
        required_evidence=[],
        vector_context=[],
        graph_context=[],
        timeline_context=[],
        contradictions=[],
        risk_flags=[],
        final_answer=None,
        citations=[],
        errors=[],
    )
