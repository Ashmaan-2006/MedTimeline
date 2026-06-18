from typing import Literal

from medgraph_api.agents.state import ClinicalAgentState


ClinicalQuestionIntent = Literal[
    "timeline_summary",
    "medication_history",
    "symptom_progression",
    "diagnosis_support",
    "lab_trend",
    "contradiction_check",
    "risk_assessment",
    "general_question",
]


INTENT_REQUIRED_EVIDENCE: dict[ClinicalQuestionIntent, list[str]] = {
    "timeline_summary": ["timeline_context", "vector_context"],
    "medication_history": ["timeline_context", "graph_context", "vector_context"],
    "symptom_progression": ["timeline_context", "graph_context", "vector_context"],
    "diagnosis_support": ["graph_context", "vector_context", "citations"],
    "lab_trend": ["timeline_context", "graph_context", "vector_context"],
    "contradiction_check": ["contradictions", "graph_context", "vector_context"],
    "risk_assessment": ["risk_flags", "timeline_context", "vector_context"],
    "general_question": ["vector_context", "citations"],
}


_INTENT_KEYWORDS: dict[ClinicalQuestionIntent, tuple[str, ...]] = {
    "timeline_summary": (
        "timeline",
        "over time",
        "what happened",
        "history",
        "summarize",
        "summary",
        "progression",
    ),
    "medication_history": (
        "medication",
        "medications",
        "medicine",
        "drug",
        "dose",
        "dosage",
        "metoprolol",
        "started",
        "stopped",
        "changed",
        "prescribed",
    ),
    "symptom_progression": (
        "symptom",
        "symptoms",
        "worsen",
        "worsened",
        "worse",
        "improved",
        "better",
        "after",
        "before",
        "chest pain",
        "shortness of breath",
    ),
    "diagnosis_support": (
        "diagnosis",
        "diagnoses",
        "diagnosed",
        "differential",
        "support",
        "supports",
        "evidence for",
        "rule out",
        "explain",
    ),
    "lab_trend": (
        "lab",
        "labs",
        "test result",
        "troponin",
        "creatinine",
        "hemoglobin",
        "trend",
        "trending",
        "increased",
        "decreased",
    ),
    "contradiction_check": (
        "contradiction",
        "contradict",
        "conflict",
        "conflicting",
        "inconsistent",
        "mismatch",
        "disagree",
        "missing",
    ),
    "risk_assessment": (
        "risk",
        "danger",
        "warning",
        "red flag",
        "deterioration",
        "deteriorated",
        "urgent",
        "unsafe",
        "adverse",
    ),
    "general_question": (),
}


def classify_clinical_intent(question: str) -> ClinicalQuestionIntent:
    normalized_question = question.strip().lower()
    if not normalized_question:
        return "general_question"

    scored_intents = {
        intent: sum(keyword in normalized_question for keyword in keywords)
        for intent, keywords in _INTENT_KEYWORDS.items()
    }

    if scored_intents["symptom_progression"] and scored_intents["medication_history"]:
        return "symptom_progression"

    best_intent = max(scored_intents, key=scored_intents.get)
    if scored_intents[best_intent] == 0:
        return "general_question"
    return best_intent


def classify_intent_node(state: ClinicalAgentState) -> ClinicalAgentState:
    question = state.get("user_question", "")
    intent = classify_clinical_intent(question)

    next_state = state.copy()
    next_state["intent"] = intent
    next_state["required_evidence"] = INTENT_REQUIRED_EVIDENCE[intent].copy()

    if not question.strip():
        next_state["errors"] = [
            *state.get("errors", []),
            "Question intent could not be classified because the question is empty.",
        ]

    return next_state
