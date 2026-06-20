from typing import Any, get_type_hints

from langgraph.graph import StateGraph

from medgraph_api.agents.state import (
    ClinicalAgentState,
    create_initial_clinical_agent_state,
)
from medgraph_api.core.agent_config import create_state_graph


EXPECTED_STATE_KEYS = {
    "patient_id",
    "user_question",
    "intent",
    "evidence_plan",
    "required_evidence",
    "vector_context",
    "graph_context",
    "timeline_context",
    "contradictions",
    "risk_flags",
    "final_answer",
    "answer_confidence",
    "limitations",
    "citations",
    "errors",
}


def test_clinical_agent_state_defines_expected_workflow_keys() -> None:
    assert set(ClinicalAgentState.__annotations__) == EXPECTED_STATE_KEYS


def test_clinical_agent_state_has_structured_type_hints() -> None:
    hints = get_type_hints(ClinicalAgentState)

    assert hints["patient_id"] is str
    assert hints["user_question"] is str
    assert hints["intent"] == str | None
    assert hints["evidence_plan"] == dict[str, Any] | None
    assert hints["required_evidence"] == list[str]
    assert hints["vector_context"] == list[dict[str, Any]]
    assert hints["graph_context"] == list[dict[str, Any]]
    assert hints["timeline_context"] == list[dict[str, Any]]
    assert hints["contradictions"] == list[dict[str, Any]]
    assert hints["risk_flags"] == list[dict[str, Any]]
    assert hints["final_answer"] == str | None
    assert hints["answer_confidence"] == str | None
    assert hints["limitations"] == list[str]
    assert hints["citations"] == list[dict[str, Any]]
    assert hints["errors"] == list[str]


def test_create_initial_clinical_agent_state_sets_empty_structured_defaults() -> None:
    state = create_initial_clinical_agent_state(
        patient_id="patient-1",
        user_question="Did symptoms worsen?",
    )

    assert state == {
        "patient_id": "patient-1",
        "user_question": "Did symptoms worsen?",
        "intent": None,
        "evidence_plan": None,
        "required_evidence": [],
        "vector_context": [],
        "graph_context": [],
        "timeline_context": [],
        "contradictions": [],
        "risk_flags": [],
        "final_answer": None,
        "answer_confidence": None,
        "limitations": [],
        "citations": [],
        "errors": [],
    }


def test_initial_clinical_agent_state_lists_are_not_shared() -> None:
    first_state = create_initial_clinical_agent_state("patient-1", "Question one")
    second_state = create_initial_clinical_agent_state("patient-1", "Question two")

    first_state["errors"].append("temporary error")

    assert first_state["errors"] == ["temporary error"]
    assert second_state["errors"] == []


def test_clinical_agent_state_can_initialize_langgraph_state_graph() -> None:
    graph = create_state_graph(ClinicalAgentState)

    assert isinstance(graph, StateGraph)
