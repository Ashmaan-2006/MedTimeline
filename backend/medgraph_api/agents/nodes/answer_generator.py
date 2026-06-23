from typing import Any, Literal, TypedDict

from medgraph_api.agents.nodes.risk_flagger import RISK_DISCLAIMER
from medgraph_api.agents.state import ClinicalAgentState
from medgraph_api.core.config import get_settings
from medgraph_api.services.model_fallback import ModelFallbackRunner


AnswerConfidence = Literal["low", "medium", "high"]


class GroundedClinicalAnswer(TypedDict):
    answer: str
    citations: list[dict[str, Any]]
    confidence: AnswerConfidence
    limitations: list[str]


class GroundedAnswerGenerationNode:
    def __call__(self, state: ClinicalAgentState) -> ClinicalAgentState:
        return generate_grounded_answer_node(state)


def generate_grounded_answer_node(state: ClinicalAgentState) -> ClinicalAgentState:
    answer_payload = generate_grounded_clinical_answer(state)

    next_state = state.copy()
    next_state["final_answer"] = answer_payload["answer"]
    next_state["citations"] = answer_payload["citations"]
    next_state["answer_confidence"] = answer_payload["confidence"]
    next_state["limitations"] = answer_payload["limitations"]
    return next_state


def generate_grounded_clinical_answer(state: ClinicalAgentState) -> GroundedClinicalAnswer:
    settings = get_settings()
    result = ModelFallbackRunner(settings.agent_timeout_seconds).run(
        primary=lambda: _generate_grounded_clinical_answer(state),
        fallback=lambda: _generate_fallback_clinical_answer(state),
        operation_name="answer_generation",
    )
    answer_payload = result.output
    if result.used_fallback:
        warning = result.warning or "Primary answer model failed; fallback answer was used."
        answer_payload["answer"] = f"{answer_payload['answer']} {warning}"
        answer_payload["confidence"] = "low"
        answer_payload["limitations"] = [*answer_payload["limitations"], warning]
    return answer_payload


def _generate_grounded_clinical_answer(state: ClinicalAgentState) -> GroundedClinicalAnswer:
    citations = collect_citations(state)
    limitations = identify_limitations(state, citations)

    if not citations:
        return GroundedClinicalAnswer(
            answer=(
                "Insufficient evidence was retrieved to answer this question. "
                f"{RISK_DISCLAIMER}"
            ),
            citations=[],
            confidence="low",
            limitations=["No vector, graph, timeline, contradiction, or risk evidence was available."],
        )

    answer_sections = []
    timeline_summary = build_timeline_summary(state.get("timeline_context", []), citations)
    if timeline_summary:
        answer_sections.append(timeline_summary)

    graph_summary = build_graph_summary(state.get("graph_context", []), citations)
    if graph_summary:
        answer_sections.append(graph_summary)

    contradiction_summary = build_contradiction_summary(state.get("contradictions", []), citations)
    if contradiction_summary:
        answer_sections.append(contradiction_summary)

    risk_summary = build_risk_summary(state.get("risk_flags", []), citations)
    if risk_summary:
        answer_sections.append(risk_summary)

    if not answer_sections:
        answer_sections.append(build_vector_summary(state.get("vector_context", []), citations))

    answer = " ".join(section for section in answer_sections if section)
    answer = (
        f"{answer} This is an evidence-grounded summary, not a diagnosis. "
        f"Uncertainty remains where retrieved records are incomplete. {RISK_DISCLAIMER}"
    )

    return GroundedClinicalAnswer(
        answer=answer,
        citations=citations,
        confidence=estimate_confidence(citations, limitations, state.get("contradictions", [])),
        limitations=limitations,
    )


def _generate_fallback_clinical_answer(state: ClinicalAgentState) -> GroundedClinicalAnswer:
    citations = collect_citations(state)
    if not citations:
        return GroundedClinicalAnswer(
            answer=(
                "Fallback answer generation could not find retrieved evidence to support an "
                f"answer. {RISK_DISCLAIMER}"
            ),
            citations=[],
            confidence="low",
            limitations=["Fallback answer generation had no retrieved evidence available."],
        )

    first_citation = citations[0]
    snippet = first_citation.get("snippet") or "retrieved clinical evidence"
    return GroundedClinicalAnswer(
        answer=(
            "A lower-confidence fallback answer was generated from the strongest retrieved "
            f"evidence: {snippet} {first_citation['label']}. {RISK_DISCLAIMER}"
        ),
        citations=citations,
        confidence="low",
        limitations=[
            "Fallback answer generation was used, so the response is intentionally conservative."
        ],
    )


def collect_citations(state: ClinicalAgentState) -> list[dict[str, Any]]:
    citations = []
    citations.extend(collect_vector_citations(state.get("vector_context", []), len(citations)))
    citations.extend(collect_timeline_citations(state.get("timeline_context", []), len(citations)))
    citations.extend(collect_graph_citations(state.get("graph_context", []), len(citations)))
    citations.extend(collect_contradiction_citations(state.get("contradictions", []), len(citations)))
    citations.extend(collect_risk_citations(state.get("risk_flags", []), len(citations)))
    return deduplicate_citations(citations)


def collect_vector_citations(
    vector_context: list[dict[str, Any]],
    start_index: int,
) -> list[dict[str, Any]]:
    citations = []
    for index, item in enumerate(vector_context, start=start_index + 1):
        citations.append(
            {
                "label": f"[{index}]",
                "source_type": "vector_chunk",
                "evidence_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
                "snippet": item.get("source_snippet") or item.get("content"),
            }
        )
    return citations


def collect_graph_citations(
    graph_context: list[dict[str, Any]],
    start_index: int,
) -> list[dict[str, Any]]:
    citations = []
    index = start_index
    for section in graph_context:
        for item in section.get("items", []):
            snippet = item.get("evidence") or item.get("content") or item.get("title")
            if not snippet:
                snippet = format_graph_item_snippet(item)
            if not snippet:
                continue
            index += 1
            citations.append(
                {
                    "label": f"[{index}]",
                    "source_type": f"graph_{section.get('type', 'context')}",
                    "evidence_id": item.get("chunk_id")
                    or item.get("source_chunk_id")
                    or item.get("event_id"),
                    "document_id": item.get("document_id"),
                    "snippet": snippet,
                }
            )
    return citations


def collect_timeline_citations(
    timeline_context: list[dict[str, Any]],
    start_index: int,
) -> list[dict[str, Any]]:
    citations = []
    for index, item in enumerate(timeline_context, start=start_index + 1):
        citations.append(
            {
                "label": f"[{index}]",
                "source_type": "timeline_event",
                "evidence_id": item.get("chunk_id") or item.get("event_id"),
                "document_id": item.get("document_id"),
                "snippet": item.get("summary") or item.get("narrative"),
            }
        )
    return citations


def collect_contradiction_citations(
    contradictions: list[dict[str, Any]],
    start_index: int,
) -> list[dict[str, Any]]:
    citations = []
    for index, contradiction in enumerate(contradictions, start=start_index + 1):
        citations.append(
            {
                "label": f"[{index}]",
                "source_type": "contradiction",
                "evidence_id": contradiction.get("evidence_a"),
                "related_evidence_id": contradiction.get("evidence_b"),
                "document_id": None,
                "snippet": (
                    f"{contradiction.get('claim_a')} / {contradiction.get('claim_b')}"
                ),
            }
        )
    return citations


def collect_risk_citations(
    risk_flags: list[dict[str, Any]],
    start_index: int,
) -> list[dict[str, Any]]:
    citations = []
    for index, risk_flag in enumerate(risk_flags, start=start_index + 1):
        citations.append(
            {
                "label": f"[{index}]",
                "source_type": "risk_flag",
                "evidence_id": risk_flag.get("evidence_ids", [None])[0]
                if risk_flag.get("evidence_ids")
                else None,
                "document_id": None,
                "snippet": f"{risk_flag.get('title')}: {risk_flag.get('rationale')}",
            }
        )
    return citations


def build_timeline_summary(
    timeline_context: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    if not timeline_context:
        return ""
    cited_events = []
    for event in timeline_context[:3]:
        citation_label = find_citation_label(citations, event.get("chunk_id") or event.get("event_id"))
        cited_events.append(
            f"{event.get('display_date', 'An available date')}: "
            f"{event.get('summary', 'timeline evidence was noted')} {citation_label}"
        )
    return "Timeline evidence shows " + "; ".join(cited_events) + "."


def build_graph_summary(
    graph_context: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    relationships = [
        item
        for section in graph_context
        if section.get("type") == "relationships"
        for item in section.get("items", [])
    ]
    if not relationships:
        return ""

    relationship = relationships[0]
    citation_label = find_citation_label(
        citations,
        relationship.get("source_chunk_id"),
        fallback_source_type="graph_relationships",
    )
    relationship_text = str(relationship.get("relationship_type", "related to")).lower()
    relationship_text = relationship_text.replace("_", " ")
    return (
        "Graph evidence links "
        f"{relationship.get('source_name')} {relationship_text} "
        f"{relationship.get('target_name')} {citation_label}."
    )


def build_contradiction_summary(
    contradictions: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    if not contradictions:
        return ""
    contradiction = contradictions[0]
    citation_label = find_citation_label(citations, contradiction.get("evidence_a"))
    return (
        "The retrieved record set contains conflicting documentation: "
        f"{contradiction.get('claim_a')} versus {contradiction.get('claim_b')} "
        f"{citation_label}."
    )


def build_risk_summary(
    risk_flags: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    if not risk_flags:
        return ""
    flag = risk_flags[0]
    evidence_ids = flag.get("evidence_ids") or []
    citation_label = find_citation_label(citations, evidence_ids[0] if evidence_ids else None)
    return (
        "Risk-signal review flags "
        f"{flag.get('title', 'a documentation concern').lower()}: "
        f"{flag.get('rationale')} {citation_label}."
    )


def build_vector_summary(
    vector_context: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    if not vector_context:
        return ""
    item = vector_context[0]
    citation_label = find_citation_label(citations, item.get("chunk_id"))
    return (
        "Retrieved document evidence states: "
        f"{item.get('source_snippet') or item.get('content')} {citation_label}."
    )


def identify_limitations(
    state: ClinicalAgentState,
    citations: list[dict[str, Any]],
) -> list[str]:
    limitations = []
    if not state.get("timeline_context"):
        limitations.append("No ordered timeline evidence was available in the retrieved context.")
    if not state.get("graph_context"):
        limitations.append("No clinical graph relationship evidence was available.")
    if not has_lab_evidence(citations):
        limitations.append("No lab report evidence was available in the retrieved context.")
    if state.get("contradictions"):
        limitations.append("Conflicting documentation lowers certainty and requires clinician review.")
    return limitations


def estimate_confidence(
    citations: list[dict[str, Any]],
    limitations: list[str],
    contradictions: list[dict[str, Any]],
) -> AnswerConfidence:
    if len(citations) >= 4 and not limitations and not contradictions:
        return "high"
    if len(citations) >= 2 and len(limitations) <= 3:
        return "medium"
    return "low"


def has_lab_evidence(citations: list[dict[str, Any]]) -> bool:
    lab_terms = ("troponin", "creatinine", "hemoglobin", "lab")
    return any(
        any(term in str(citation.get("snippet", "")).lower() for term in lab_terms)
        for citation in citations
    )


def find_citation_label(
    citations: list[dict[str, Any]],
    evidence_id: str | None,
    fallback_source_type: str | None = None,
) -> str:
    if evidence_id:
        for citation in citations:
            if citation.get("evidence_id") == evidence_id:
                return citation["label"]
    if fallback_source_type:
        for citation in citations:
            if citation.get("source_type") == fallback_source_type:
                return citation["label"]
    return citations[0]["label"] if citations else ""


def format_graph_item_snippet(item: dict[str, Any]) -> str:
    if item.get("source_name") and item.get("target_name"):
        relationship = str(item.get("relationship_type", "related to")).lower().replace("_", " ")
        return f"{item.get('source_name')} {relationship} {item.get('target_name')}"
    return ""


def deduplicate_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduplicated = []
    seen_keys = set()
    for citation in citations:
        key = (
            citation.get("source_type"),
            citation.get("evidence_id"),
            citation.get("related_evidence_id"),
            citation.get("snippet"),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduplicated.append({**citation, "label": f"[{len(deduplicated) + 1}]"})
    return deduplicated
