from datetime import UTC, datetime, time
from typing import Any
from uuid import UUID

from medgraph_api.agents.state import ClinicalAgentState
from medgraph_api.services.retrieval_filters import RetrievalFilters
from medgraph_api.services.similarity_search import (
    PatientDocumentSearchResult,
    PatientDocumentSimilaritySearchService,
)


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
    next_state["vector_context"] = [format_vector_context(result) for result in results]
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


def format_vector_context(result: PatientDocumentSearchResult) -> dict[str, Any]:
    return {
        "chunk_id": str(result.chunk_id),
        "document_id": str(result.document_id),
        "patient_id": str(result.patient_id),
        "chunk_index": result.chunk_index,
        "content": result.content,
        "source_snippet": build_source_snippet(result.content),
        "similarity_score": getattr(result, "similarity_score", None),
        "embedding_model": result.embedding_model,
        "token_count": result.token_count,
        "chunk_metadata": result.chunk_metadata,
        "created_at": result.created_at.isoformat(),
    }


def build_source_snippet(content: str, max_length: int = 280) -> str:
    normalized_content = " ".join(content.split())
    if len(normalized_content) <= max_length:
        return normalized_content

    truncated = normalized_content[: max_length - 3].rstrip()
    word_boundary = truncated.rfind(" ")
    if word_boundary > 0:
        truncated = truncated[:word_boundary]
    return truncated + "..."


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
