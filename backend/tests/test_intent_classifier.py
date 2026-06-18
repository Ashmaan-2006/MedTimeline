from medgraph_api.agents.nodes.intent_classifier import (
    INTENT_REQUIRED_EVIDENCE,
    classify_clinical_intent,
    classify_intent_node,
)
from medgraph_api.agents.state import create_initial_clinical_agent_state


def test_classify_clinical_intent_detects_symptom_progression_after_medication() -> None:
    intent = classify_clinical_intent("Did symptoms worsen after metoprolol?")

    assert intent == "symptom_progression"


def test_classify_clinical_intent_detects_supported_intent_types() -> None:
    examples = {
        "Summarize what happened over time": "timeline_summary",
        "What medications were started or stopped?": "medication_history",
        "What evidence supports atrial fibrillation?": "diagnosis_support",
        "Did troponin trend upward?": "lab_trend",
        "Are there conflicting notes about allergies?": "contradiction_check",
        "What red flags suggest deterioration?": "risk_assessment",
        "Who was the ordering provider?": "general_question",
    }

    for question, expected_intent in examples.items():
        assert classify_clinical_intent(question) == expected_intent


def test_classify_intent_node_updates_structured_agent_state() -> None:
    state = create_initial_clinical_agent_state(
        patient_id="patient-1",
        user_question="Did symptoms worsen after metoprolol?",
    )

    next_state = classify_intent_node(state)

    assert next_state["intent"] == "symptom_progression"
    assert next_state["required_evidence"] == INTENT_REQUIRED_EVIDENCE["symptom_progression"]
    assert next_state["patient_id"] == "patient-1"
    assert next_state["user_question"] == "Did symptoms worsen after metoprolol?"
    assert next_state["errors"] == []


def test_classify_intent_node_records_empty_question_error() -> None:
    state = create_initial_clinical_agent_state(
        patient_id="patient-1",
        user_question=" ",
    )

    next_state = classify_intent_node(state)

    assert next_state["intent"] == "general_question"
    assert next_state["required_evidence"] == INTENT_REQUIRED_EVIDENCE["general_question"]
    assert next_state["errors"] == [
        "Question intent could not be classified because the question is empty."
    ]
