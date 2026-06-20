import re
from typing import Any, Literal

from medgraph_api.agents.state import ClinicalAgentState


RISK_DISCLAIMER = "Not medical advice. Review with a qualified clinician."

RiskCategory = Literal[
    "worsening_symptoms",
    "abnormal_lab",
    "repeated_emergency_visits",
    "medication_discontinuity",
    "missing_follow_up",
    "conflicting_records",
]


class ClinicalRiskFlaggingNode:
    def __call__(self, state: ClinicalAgentState) -> ClinicalAgentState:
        return flag_clinical_risks_node(state)


def flag_clinical_risks_node(state: ClinicalAgentState) -> ClinicalAgentState:
    risk_flags = detect_risk_flags(state)

    next_state = state.copy()
    next_state["risk_flags"] = risk_flags
    return next_state


def detect_risk_flags(state: ClinicalAgentState) -> list[dict[str, Any]]:
    text_evidence = collect_text_evidence(state)
    risk_flags = []
    risk_flags.extend(detect_worsening_symptoms(text_evidence))
    risk_flags.extend(detect_abnormal_labs(text_evidence))
    risk_flags.extend(detect_repeated_emergency_visits(text_evidence))
    risk_flags.extend(detect_medication_discontinuity(text_evidence))
    risk_flags.extend(detect_missing_follow_up(text_evidence))
    risk_flags.extend(detect_conflicting_records(state.get("contradictions", [])))
    return deduplicate_risk_flags(risk_flags)


def collect_text_evidence(state: ClinicalAgentState) -> list[dict[str, Any]]:
    evidence = []
    evidence.extend(collect_vector_evidence(state.get("vector_context", [])))
    evidence.extend(collect_graph_evidence(state.get("graph_context", [])))
    evidence.extend(collect_timeline_evidence(state.get("timeline_context", [])))
    return evidence


def collect_vector_evidence(vector_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "text": chunk.get("source_snippet") or chunk.get("content") or "",
            "evidence_id": chunk.get("chunk_id"),
            "source": "vector_context",
        }
        for chunk in vector_context
    ]


def collect_graph_evidence(graph_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence = []
    for section in graph_context:
        for item in section.get("items", []):
            text_parts = [
                item.get("evidence"),
                item.get("content"),
                item.get("title"),
                item.get("source_name"),
                item.get("relationship_type"),
                item.get("target_name"),
            ]
            evidence.append(
                {
                    "text": " ".join(str(part) for part in text_parts if part),
                    "evidence_id": item.get("chunk_id")
                    or item.get("source_chunk_id")
                    or item.get("event_id"),
                    "source": f"graph_context:{section.get('type', 'unknown')}",
                }
            )
    return evidence


def collect_timeline_evidence(timeline_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "text": event.get("summary") or event.get("narrative") or "",
            "evidence_id": event.get("chunk_id") or event.get("event_id"),
            "source": "timeline_context",
        }
        for event in timeline_context
    ]


def detect_worsening_symptoms(text_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flags = []
    symptom_terms = ("shortness of breath", "dyspnea", "chest pain", "dizziness")
    worsening_terms = ("worsening", "worsened", "worse", "progressive", "deteriorated")
    for item in text_evidence:
        normalized_text = normalize_text(item["text"])
        if any(symptom in normalized_text for symptom in symptom_terms) and any(
            term in normalized_text for term in worsening_terms
        ):
            flags.append(
                build_risk_flag(
                    category="worsening_symptoms",
                    title="Worsening symptom signal",
                    rationale="Evidence mentions symptoms worsening or clinical deterioration.",
                    severity="high" if "chest pain" in normalized_text else "medium",
                    evidence_ids=[item.get("evidence_id")],
                    source=item.get("source"),
                )
            )
    return flags


def detect_abnormal_labs(text_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flags = []
    lab_terms = ("troponin", "creatinine", "hemoglobin")
    abnormal_terms = ("elevated", "high", "increased", "positive", "abnormal", "low")
    for item in text_evidence:
        normalized_text = normalize_text(item["text"])
        matching_labs = [lab for lab in lab_terms if lab in normalized_text]
        if matching_labs and any(term in normalized_text for term in abnormal_terms):
            flags.append(
                build_risk_flag(
                    category="abnormal_lab",
                    title="Abnormal lab mention",
                    rationale=f"Evidence mentions abnormal {', '.join(matching_labs)} results.",
                    severity="high" if "troponin" in matching_labs else "medium",
                    evidence_ids=[item.get("evidence_id")],
                    source=item.get("source"),
                )
            )
    return flags


def detect_repeated_emergency_visits(text_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    emergency_items = [
        item
        for item in text_evidence
        if re.search(r"\b(ed|er|emergency|emergency department)\b", normalize_text(item["text"]))
    ]
    if len(emergency_items) < 2:
        return []

    return [
        build_risk_flag(
            category="repeated_emergency_visits",
            title="Repeated emergency care mentions",
            rationale="Multiple evidence items mention emergency or ED visits.",
            severity="medium",
            evidence_ids=[item.get("evidence_id") for item in emergency_items],
            source=";".join(sorted({str(item.get("source")) for item in emergency_items})),
        )
    ]


def detect_medication_discontinuity(text_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flags = []
    medications = ("metoprolol", "warfarin", "aspirin", "lisinopril", "atorvastatin")
    discontinuity_terms = ("stopped", "discontinued", "held", "withheld", "restarted", "resumed")
    for item in text_evidence:
        normalized_text = normalize_text(item["text"])
        matching_medications = [
            medication for medication in medications if medication in normalized_text
        ]
        if matching_medications and any(term in normalized_text for term in discontinuity_terms):
            flags.append(
                build_risk_flag(
                    category="medication_discontinuity",
                    title="Medication continuity concern",
                    rationale=(
                        f"Evidence mentions medication status changes for "
                        f"{', '.join(matching_medications)}."
                    ),
                    severity="medium",
                    evidence_ids=[item.get("evidence_id")],
                    source=item.get("source"),
                )
            )
    return flags


def detect_missing_follow_up(text_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flags = []
    missing_follow_up_patterns = (
        "no follow up",
        "no follow-up",
        "missed follow up",
        "missed follow-up",
        "lost to follow up",
        "lost to follow-up",
        "follow up not documented",
        "follow-up not documented",
    )
    for item in text_evidence:
        normalized_text = normalize_text(item["text"])
        if any(pattern in normalized_text for pattern in missing_follow_up_patterns):
            flags.append(
                build_risk_flag(
                    category="missing_follow_up",
                    title="Follow-up documentation concern",
                    rationale="Evidence suggests follow-up may be missing or not documented.",
                    severity="medium",
                    evidence_ids=[item.get("evidence_id")],
                    source=item.get("source"),
                )
            )
    return flags


def detect_conflicting_records(contradictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        build_risk_flag(
            category="conflicting_records",
            title="Conflicting record evidence",
            rationale=(
                "Contradiction detection found conflicting documentation for "
                f"{contradiction.get('subject', 'a clinical item')}."
            ),
            severity=contradiction.get("severity", "medium"),
            evidence_ids=[contradiction.get("evidence_a"), contradiction.get("evidence_b")],
            source="contradictions",
        )
        for contradiction in contradictions
    ]


def build_risk_flag(
    category: RiskCategory,
    title: str,
    rationale: str,
    severity: str,
    evidence_ids: list[str | None],
    source: str | None,
) -> dict[str, Any]:
    return {
        "category": category,
        "title": title,
        "rationale": rationale,
        "severity": severity,
        "evidence_ids": [evidence_id for evidence_id in evidence_ids if evidence_id],
        "source": source,
        "disclaimer": RISK_DISCLAIMER,
    }


def deduplicate_risk_flags(risk_flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduplicated = []
    seen_keys = set()
    for flag in risk_flags:
        key = (
            flag["category"],
            flag["title"],
            tuple(sorted(flag["evidence_ids"])),
            flag["rationale"],
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduplicated.append(flag)
    return deduplicated


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()
