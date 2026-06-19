from medgraph_api.agents.nodes.evidence_planner import (
    extract_date_range,
    extract_target_entities,
    plan_evidence,
    plan_evidence_node,
)
from medgraph_api.agents.state import create_initial_clinical_agent_state


def test_plan_evidence_for_symptom_progression_uses_hybrid_retrieval() -> None:
    plan = plan_evidence(
        question="Did symptoms worsen after metoprolol with shortness of breath?",
        intent="symptom_progression",
    )

    assert plan == {
        "needs_vector_search": True,
        "needs_graph_search": True,
        "needs_timeline": True,
        "target_entities": ["shortness of breath", "metoprolol"],
        "date_range": None,
        "required_evidence": ["symptoms", "medications", "timeline_events"],
    }


def test_plan_evidence_for_general_question_defaults_to_vector_search() -> None:
    plan = plan_evidence(
        question="Who wrote the note?",
        intent=None,
    )

    assert plan["needs_vector_search"] is True
    assert plan["needs_graph_search"] is False
    assert plan["needs_timeline"] is False
    assert plan["required_evidence"] == ["source_chunks"]


def test_plan_evidence_node_updates_agent_state() -> None:
    state = create_initial_clinical_agent_state(
        patient_id="patient-1",
        user_question="Did symptoms worsen after metoprolol?",
    )
    state["intent"] = "symptom_progression"

    next_state = plan_evidence_node(state)

    assert next_state["evidence_plan"] == {
        "needs_vector_search": True,
        "needs_graph_search": True,
        "needs_timeline": True,
        "target_entities": ["metoprolol"],
        "date_range": None,
        "required_evidence": ["symptoms", "medications", "timeline_events"],
    }
    assert next_state["required_evidence"] == ["symptoms", "medications", "timeline_events"]


def test_extract_target_entities_includes_known_phrases_and_capitalized_terms() -> None:
    entities = extract_target_entities("Compare Metoprolol, troponin, and chest pain.")

    assert entities == ["chest pain", "metoprolol", "troponin"]


def test_extract_date_range_from_iso_dates() -> None:
    date_range = extract_date_range("Compare labs from 2026-01-05 to 2026-02-07")

    assert date_range == {"start": "2026-01-05", "end": "2026-02-07"}


def test_extract_date_range_from_month_year() -> None:
    date_range = extract_date_range("What happened during February 2026?")

    assert date_range == {"start": "2026-02-01", "end": "2026-02-28"}
