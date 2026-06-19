import re
from datetime import date
from typing import Any, Literal, TypedDict

from medgraph_api.agents.nodes.intent_classifier import ClinicalQuestionIntent
from medgraph_api.agents.state import ClinicalAgentState


EvidenceDateRange = dict[Literal["start", "end"], str | None]


class EvidencePlan(TypedDict):
    needs_vector_search: bool
    needs_graph_search: bool
    needs_timeline: bool
    target_entities: list[str]
    date_range: EvidenceDateRange | None
    required_evidence: list[str]


_PLAN_BY_INTENT: dict[ClinicalQuestionIntent, dict[str, Any]] = {
    "timeline_summary": {
        "needs_vector_search": True,
        "needs_graph_search": False,
        "needs_timeline": True,
        "required_evidence": ["timeline_events", "document_chunks"],
    },
    "medication_history": {
        "needs_vector_search": True,
        "needs_graph_search": True,
        "needs_timeline": True,
        "required_evidence": ["medications", "timeline_events", "source_chunks"],
    },
    "symptom_progression": {
        "needs_vector_search": True,
        "needs_graph_search": True,
        "needs_timeline": True,
        "required_evidence": ["symptoms", "medications", "timeline_events"],
    },
    "diagnosis_support": {
        "needs_vector_search": True,
        "needs_graph_search": True,
        "needs_timeline": False,
        "required_evidence": ["diagnoses", "findings", "source_chunks"],
    },
    "lab_trend": {
        "needs_vector_search": True,
        "needs_graph_search": True,
        "needs_timeline": True,
        "required_evidence": ["lab_tests", "lab_results", "timeline_events"],
    },
    "contradiction_check": {
        "needs_vector_search": True,
        "needs_graph_search": True,
        "needs_timeline": True,
        "required_evidence": ["conflicting_claims", "source_chunks", "timeline_events"],
    },
    "risk_assessment": {
        "needs_vector_search": True,
        "needs_graph_search": True,
        "needs_timeline": True,
        "required_evidence": ["risk_flags", "symptoms", "timeline_events"],
    },
    "general_question": {
        "needs_vector_search": True,
        "needs_graph_search": False,
        "needs_timeline": False,
        "required_evidence": ["source_chunks"],
    },
}

_STOP_WORDS = {
    "a",
    "after",
    "and",
    "are",
    "before",
    "between",
    "compare",
    "did",
    "during",
    "for",
    "from",
    "has",
    "have",
    "how",
    "in",
    "is",
    "of",
    "on",
    "patient",
    "the",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "why",
    "with",
    "worse",
    "worsen",
    "worsened",
}

_ENTITY_PHRASES = (
    "shortness of breath",
    "chest pain",
    "atrial fibrillation",
    "heart failure",
    "blood pressure",
    "st elevation",
    "metoprolol",
    "troponin",
    "creatinine",
    "hemoglobin",
    "ecg",
)

_MONTHS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}


def plan_evidence(question: str, intent: str | None) -> EvidencePlan:
    clinical_intent = _coerce_intent(intent)
    template = _PLAN_BY_INTENT[clinical_intent]

    return EvidencePlan(
        needs_vector_search=template["needs_vector_search"],
        needs_graph_search=template["needs_graph_search"],
        needs_timeline=template["needs_timeline"],
        target_entities=extract_target_entities(question),
        date_range=extract_date_range(question),
        required_evidence=template["required_evidence"].copy(),
    )


def plan_evidence_node(state: ClinicalAgentState) -> ClinicalAgentState:
    evidence_plan = plan_evidence(
        question=state.get("user_question", ""),
        intent=state.get("intent"),
    )

    next_state = state.copy()
    next_state["evidence_plan"] = evidence_plan
    next_state["required_evidence"] = evidence_plan["required_evidence"].copy()
    return next_state


def extract_target_entities(question: str) -> list[str]:
    normalized_question = question.lower()
    entities = [
        phrase
        for phrase in _ENTITY_PHRASES
        if re.search(rf"\b{re.escape(phrase)}\b", normalized_question)
    ]

    capitalized_entities = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", question)
    entities.extend(
        entity.lower()
        for entity in capitalized_entities
        if entity.lower() not in _STOP_WORDS and len(entity) > 2
    )

    return list(dict.fromkeys(entities))


def extract_date_range(question: str) -> EvidenceDateRange | None:
    normalized_question = question.lower()

    iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", normalized_question)
    if len(iso_dates) >= 2:
        return {"start": iso_dates[0], "end": iso_dates[1]}
    if len(iso_dates) == 1:
        return {"start": iso_dates[0], "end": iso_dates[0]}

    month_year_match = re.search(
        r"\b("
        + "|".join(_MONTHS)
        + r")\s+(\d{4})\b",
        normalized_question,
    )
    if month_year_match:
        month, year = month_year_match.groups()
        month_number = _MONTHS[month]
        end_day = _last_day_of_month(int(year), int(month_number))
        return {
            "start": f"{year}-{month_number}-01",
            "end": f"{year}-{month_number}-{end_day:02d}",
        }

    return None


def _coerce_intent(intent: str | None) -> ClinicalQuestionIntent:
    if intent in _PLAN_BY_INTENT:
        return intent
    return "general_question"


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month.replace(day=1).toordinal() - date(year, month, 1).toordinal())
