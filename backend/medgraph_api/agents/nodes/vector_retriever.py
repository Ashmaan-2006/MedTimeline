from datetime import UTC, datetime, time
from typing import Any
from uuid import UUID

from medgraph_api.agents.state import ClinicalAgentState
from medgraph_api.services.retrieval_filters import RetrievalFilters
from medgraph_api.services.similarity_search import (
    PatientDocumentSearchResult,
    PatientDocumentSimilaritySearchService,
)
from medgraph_api.services.clinical_text import iter_passages, select_relevant_passages
from medgraph_api.services.text_snippets import build_source_snippet


class VectorRetrievalNode:
    def __init__(
        self,
        similarity_search: PatientDocumentSimilaritySearchService,
        limit: int = 5,
    ) -> None:
        self.similarity_search = similarity_search
        self.limit = limit

    def __call__(self, state: ClinicalAgentState) -> ClinicalAgentState:
        return retrieve_vector_context_node(
            state=state,
            similarity_search=self.similarity_search,
            limit=self.limit,
        )


def retrieve_vector_context_node(
    state: ClinicalAgentState,
    similarity_search: PatientDocumentSimilaritySearchService,
    limit: int = 5,
) -> ClinicalAgentState:
    evidence_plan = state.get("evidence_plan") or {}
    if evidence_plan.get("needs_vector_search") is False:
        next_state = state.copy()
        next_state["vector_context"] = []
        return next_state

    try:
        patient_id = UUID(state["patient_id"])
    except (KeyError, ValueError):
        return _append_error(state, "Vector retrieval skipped because patient_id is not a valid UUID.")

    query = build_vector_query(
        question=state.get("user_question", ""),
        target_entities=evidence_plan.get("target_entities") or [],
    )
    filters = build_retrieval_filters(evidence_plan)

    try:
        results = similarity_search.search(
            patient_id=patient_id,
            query=query,
            limit=limit,
            filters=filters,
        )
    except Exception:
        return _append_error(state, "Vector retrieval failed.")

    next_state = state.copy()
    next_state["vector_context"] = [
        format_vector_context(result, question=state.get("user_question", ""))
        for result in results
    ]
    return next_state


def build_vector_query(question: str, target_entities: list[str]) -> str:
    query_parts = [" ".join(question.split())]
    query_parts.extend(entity.strip() for entity in target_entities if entity.strip())
    return " ".join(part for part in query_parts if part)


def build_retrieval_filters(evidence_plan: dict[str, Any]) -> RetrievalFilters | None:
    date_range = evidence_plan.get("date_range")
    if not isinstance(date_range, dict):
        return None

    return RetrievalFilters(
        created_from=_parse_date_boundary(date_range.get("start"), end_of_day=False),
        created_to=_parse_date_boundary(date_range.get("end"), end_of_day=True),
    )


def format_vector_context(
    result: PatientDocumentSearchResult,
    question: str = "",
) -> dict[str, Any]:
    return {
        "chunk_id": str(result.chunk_id),
        "document_id": str(result.document_id),
        "patient_id": str(result.patient_id),
        "chunk_index": result.chunk_index,
        "content": result.content,
        "source_snippet": build_source_snippet(result.content),
        "relevant_snippet": build_relevant_snippet(
            result.content,
            question=question,
            section=(result.chunk_metadata or {}).get("section"),
        ),
        "similarity_score": getattr(result, "similarity_score", None),
        "embedding_model": result.embedding_model,
        "token_count": result.token_count,
        "chunk_metadata": result.chunk_metadata,
        "created_at": result.created_at.isoformat(),
    }


def build_relevant_snippet(
    content: str,
    question: str,
    section: str | None = None,
    max_length: int = 280,
) -> str:
    """Quote the sentences in a chunk that address the question, not just its opening."""
    passages = iter_passages(content, initial_section=section)
    selected = select_relevant_passages(passages, question, limit=2)
    if not selected:
        return build_source_snippet(content, max_length=max_length)
    if len(selected) > 1 and len({passage.heading for passage in selected}) == 1:
        # Same section: "Unchanged Medications: Proferrin ...; Ramipril ..." reads better
        # than repeating the heading for each item.
        joined = "; ".join(passage.text.rstrip(".") for passage in selected)
        text = f"{selected[0].heading}: {joined}." if selected[0].heading else f"{joined}."
        return build_source_snippet(text, max_length=max_length)
    sentences = [
        text if text.endswith((".", "!", "?")) else f"{text}."
        for text in (passage.display_text() for passage in selected)
    ]
    return build_source_snippet(" ".join(sentences), max_length=max_length)


def _parse_date_boundary(value: str | None, end_of_day: bool) -> datetime | None:
    if not value:
        return None

    parsed_date = datetime.fromisoformat(value)
    if parsed_date.tzinfo is not None:
        return parsed_date

    if "T" in value:
        return parsed_date.replace(tzinfo=UTC)

    boundary_time = time.max if end_of_day else time.min
    return datetime.combine(parsed_date.date(), boundary_time, tzinfo=UTC)


def _append_error(state: ClinicalAgentState, message: str) -> ClinicalAgentState:
    next_state = state.copy()
    next_state["errors"] = [*state.get("errors", []), message]
    return next_state
