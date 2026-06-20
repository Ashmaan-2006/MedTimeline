import re
from dataclasses import dataclass
from typing import Any, Literal

from medgraph_api.agents.state import ClinicalAgentState


ClaimCategory = Literal["symptom", "medication", "lab"]


@dataclass(frozen=True)
class ClinicalClaim:
    category: ClaimCategory
    subject: str
    status: str
    text: str
    evidence_id: str | None
    source: str


class ContradictionCheckingNode:
    def __call__(self, state: ClinicalAgentState) -> ClinicalAgentState:
        return check_contradictions_node(state)


def check_contradictions_node(state: ClinicalAgentState) -> ClinicalAgentState:
    claims = extract_claims_from_state(state)
    contradictions = detect_contradictions(claims)

    next_state = state.copy()
    next_state["contradictions"] = contradictions
    return next_state


def extract_claims_from_state(state: ClinicalAgentState) -> list[ClinicalClaim]:
    claims = []
    claims.extend(extract_claims_from_vector_context(state.get("vector_context", [])))
    claims.extend(extract_claims_from_graph_context(state.get("graph_context", [])))
    claims.extend(extract_claims_from_timeline_context(state.get("timeline_context", [])))
    return claims


def extract_claims_from_vector_context(vector_context: list[dict[str, Any]]) -> list[ClinicalClaim]:
    claims = []
    for chunk in vector_context:
        claims.extend(
            extract_claims_from_text(
                text=chunk.get("source_snippet") or chunk.get("content") or "",
                evidence_id=chunk.get("chunk_id"),
                source="vector_context",
            )
        )
    return claims


def extract_claims_from_graph_context(graph_context: list[dict[str, Any]]) -> list[ClinicalClaim]:
    claims = []
    for section in graph_context:
        for item in section.get("items", []):
            evidence_id = item.get("chunk_id") or item.get("source_chunk_id") or item.get("event_id")
            text_parts = [
                item.get("evidence"),
                item.get("content"),
                item.get("title"),
                item.get("source_name"),
                item.get("relationship_type"),
                item.get("target_name"),
            ]
            claims.extend(
                extract_claims_from_text(
                    text=" ".join(str(part) for part in text_parts if part),
                    evidence_id=evidence_id,
                    source=f"graph_context:{section.get('type', 'unknown')}",
                )
            )
    return claims


def extract_claims_from_timeline_context(
    timeline_context: list[dict[str, Any]],
) -> list[ClinicalClaim]:
    claims = []
    for event in timeline_context:
        claims.extend(
            extract_claims_from_text(
                text=event.get("summary") or event.get("narrative") or "",
                evidence_id=event.get("chunk_id") or event.get("event_id"),
                source="timeline_context",
            )
        )
    return claims


def extract_claims_from_text(
    text: str,
    evidence_id: str | None,
    source: str,
) -> list[ClinicalClaim]:
    normalized_text = normalize_text(text)
    if not normalized_text:
        return []

    claims = []
    claims.extend(extract_symptom_claims(normalized_text, text, evidence_id, source))
    claims.extend(extract_medication_claims(normalized_text, text, evidence_id, source))
    claims.extend(extract_lab_claims(normalized_text, text, evidence_id, source))
    return claims


def extract_symptom_claims(
    normalized_text: str,
    original_text: str,
    evidence_id: str | None,
    source: str,
) -> list[ClinicalClaim]:
    claims = []
    symptom_patterns = {
        "chest pain": ("chest pain", "chest discomfort"),
        "shortness of breath": ("shortness of breath", "dyspnea"),
        "dizziness": ("dizziness", "lightheadedness"),
    }
    negation_patterns = ("no {symptom}", "denied {symptom}", "denies {symptom}", "without {symptom}")

    for subject, aliases in symptom_patterns.items():
        if not any(alias in normalized_text for alias in aliases):
            continue

        status = "absent" if any(
            pattern.format(symptom=alias) in normalized_text
            for alias in aliases
            for pattern in negation_patterns
        ) else "present"
        claims.append(
            ClinicalClaim(
                category="symptom",
                subject=subject,
                status=status,
                text=clean_claim_text(original_text),
                evidence_id=evidence_id,
                source=source,
            )
        )
    return claims


def extract_medication_claims(
    normalized_text: str,
    original_text: str,
    evidence_id: str | None,
    source: str,
) -> list[ClinicalClaim]:
    medication_names = ("metoprolol", "lisinopril", "warfarin", "aspirin", "atorvastatin")
    stopped_terms = ("stopped", "discontinued", "held", "withheld")
    continued_terms = ("continued", "continue", "active", "taking", "maintained", "resumed")

    claims = []
    for medication in medication_names:
        if medication not in normalized_text:
            continue
        if any(term in normalized_text for term in stopped_terms):
            status = "stopped"
        elif any(term in normalized_text for term in continued_terms):
            status = "continued"
        else:
            continue
        claims.append(
            ClinicalClaim(
                category="medication",
                subject=medication,
                status=status,
                text=clean_claim_text(original_text),
                evidence_id=evidence_id,
                source=source,
            )
        )
    return claims


def extract_lab_claims(
    normalized_text: str,
    original_text: str,
    evidence_id: str | None,
    source: str,
) -> list[ClinicalClaim]:
    lab_names = ("troponin", "creatinine", "hemoglobin")
    normal_terms = ("normal", "within normal", "negative", "not elevated")
    abnormal_terms = ("elevated", "high", "increased", "positive", "abnormal")

    claims = []
    for lab_name in lab_names:
        if lab_name not in normalized_text:
            continue
        if any(term in normalized_text for term in normal_terms):
            status = "normal"
        elif any(term in normalized_text for term in abnormal_terms):
            status = "abnormal"
        else:
            continue
        claims.append(
            ClinicalClaim(
                category="lab",
                subject=lab_name,
                status=status,
                text=clean_claim_text(original_text),
                evidence_id=evidence_id,
                source=source,
            )
        )
    return claims


def detect_contradictions(claims: list[ClinicalClaim]) -> list[dict[str, Any]]:
    contradictions = []
    for index, claim_a in enumerate(claims):
        for claim_b in claims[index + 1 :]:
            if not claims_conflict(claim_a, claim_b):
                continue
            contradictions.append(format_contradiction(claim_a, claim_b))
    return deduplicate_contradictions(contradictions)


def claims_conflict(claim_a: ClinicalClaim, claim_b: ClinicalClaim) -> bool:
    if claim_a.category != claim_b.category or claim_a.subject != claim_b.subject:
        return False
    if claim_a.evidence_id and claim_a.evidence_id == claim_b.evidence_id:
        return False

    conflicting_statuses = {
        ("present", "absent"),
        ("stopped", "continued"),
        ("normal", "abnormal"),
    }
    return (claim_a.status, claim_b.status) in conflicting_statuses or (
        claim_b.status,
        claim_a.status,
    ) in conflicting_statuses


def format_contradiction(
    claim_a: ClinicalClaim,
    claim_b: ClinicalClaim,
) -> dict[str, Any]:
    return {
        "claim_a": claim_a.text,
        "claim_b": claim_b.text,
        "evidence_a": claim_a.evidence_id,
        "evidence_b": claim_b.evidence_id,
        "category": claim_a.category,
        "subject": claim_a.subject,
        "severity": contradiction_severity(claim_a),
        "source_a": claim_a.source,
        "source_b": claim_b.source,
    }


def contradiction_severity(claim: ClinicalClaim) -> str:
    if claim.category == "lab" and claim.subject == "troponin":
        return "high"
    if claim.category == "symptom" and claim.subject in {"chest pain", "shortness of breath"}:
        return "medium"
    return "low"


def deduplicate_contradictions(contradictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduplicated = []
    seen_keys = set()
    for contradiction in contradictions:
        evidence_pair = tuple(
            sorted(
                evidence
                for evidence in (contradiction.get("evidence_a"), contradiction.get("evidence_b"))
                if evidence
            )
        )
        key = (
            contradiction["category"],
            contradiction["subject"],
            evidence_pair,
            contradiction["claim_a"],
            contradiction["claim_b"],
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduplicated.append(contradiction)
    return deduplicated


def clean_claim_text(text: str, max_length: int = 180) -> str:
    cleaned = " ".join(text.split()).strip()
    if len(cleaned) <= max_length:
        return cleaned
    truncated = cleaned[: max_length - 3].rstrip()
    word_boundary = truncated.rfind(" ")
    if word_boundary > 0:
        truncated = truncated[:word_boundary]
    return truncated + "..."


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()
