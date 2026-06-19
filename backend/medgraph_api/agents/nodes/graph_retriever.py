from datetime import date, datetime
from itertools import combinations
from typing import Any

from medgraph_api.agents.state import ClinicalAgentState
from medgraph_api.services.graph_query_service import (
    ClinicalGraphQueryService,
    EntityPathStep,
    EvidenceChunk,
    GraphEntity,
    GraphRelationship,
    MedicationRelatedEvent,
    SymptomNearDate,
)


class GraphRetrievalNode:
    def __init__(
        self,
        graph_query: ClinicalGraphQueryService,
        limit: int = 5,
    ) -> None:
        self.graph_query = graph_query
        self.limit = limit

    def __call__(self, state: ClinicalAgentState) -> ClinicalAgentState:
        return retrieve_graph_context_node(
            state=state,
            graph_query=self.graph_query,
            limit=self.limit,
        )


def retrieve_graph_context_node(
    state: ClinicalAgentState,
    graph_query: ClinicalGraphQueryService,
    limit: int = 5,
) -> ClinicalAgentState:
    evidence_plan = state.get("evidence_plan") or {}
    if evidence_plan.get("needs_graph_search") is False:
        next_state = state.copy()
        next_state["graph_context"] = []
        return next_state

    patient_id = state.get("patient_id", "").strip()
    if not patient_id:
        return _append_error(state, "Graph retrieval skipped because patient_id is missing.")

    target_entities = normalize_target_entities(evidence_plan.get("target_entities") or [])
    date_range = parse_graph_date_range(evidence_plan.get("date_range"))

    try:
        graph_context = collect_graph_context(
            graph_query=graph_query,
            patient_id=patient_id,
            target_entities=target_entities,
            date_range=date_range,
            limit=limit,
        )
    except Exception:
        return _append_error(state, "Graph retrieval failed.")

    next_state = state.copy()
    next_state["graph_context"] = graph_context
    return next_state


def collect_graph_context(
    graph_query: ClinicalGraphQueryService,
    patient_id: str,
    target_entities: list[str],
    date_range: tuple[date, date] | None,
    limit: int,
) -> list[dict[str, Any]]:
    entities = graph_query.get_entities_for_patient(patient_id)
    relationships = graph_query.get_relationships_for_patient(patient_id)

    context: list[dict[str, Any]] = [
        {
            "type": "entities",
            "items": [
                format_graph_entity(entity)
                for entity in filter_entities(entities, target_entities)[:limit]
            ],
        },
        {
            "type": "relationships",
            "items": [
                format_graph_relationship(relationship)
                for relationship in filter_relationships(relationships, target_entities)[:limit]
            ],
        },
    ]

    if target_entities:
        context.append(
            {
                "type": "entity_evidence_chunks",
                "items": collect_entity_evidence_chunks(
                    graph_query=graph_query,
                    patient_id=patient_id,
                    target_entities=target_entities,
                    limit=limit,
                ),
            }
        )
        context.append(
            {
                "type": "entity_paths",
                "items": collect_entity_paths(
                    graph_query=graph_query,
                    patient_id=patient_id,
                    target_entities=target_entities,
                    limit=limit,
                ),
            }
        )
        context.append(
            {
                "type": "entity_connected_events",
                "items": collect_entity_connected_events(
                    graph_query=graph_query,
                    patient_id=patient_id,
                    target_entities=target_entities,
                    limit=limit,
                ),
            }
        )

    if date_range is not None:
        context.append(
            {
                "type": "symptoms_near_date",
                "items": [
                    format_symptom_near_date(symptom)
                    for symptom in graph_query.get_symptoms_near_date(patient_id, date_range)[:limit]
                ],
            }
        )

    return context


def normalize_target_entities(target_entities: list[str]) -> list[str]:
    normalized_entities = [
        " ".join(entity.split()).lower()
        for entity in target_entities
        if isinstance(entity, str) and entity.strip()
    ]
    return list(dict.fromkeys(normalized_entities))


def filter_entities(
    entities: list[GraphEntity],
    target_entities: list[str],
) -> list[GraphEntity]:
    if not target_entities:
        return entities
    return [
        entity
        for entity in entities
        if normalize_name(entity.normalized_name) in target_entities
        or normalize_name(entity.name or "") in target_entities
    ]


def filter_relationships(
    relationships: list[GraphRelationship],
    target_entities: list[str],
) -> list[GraphRelationship]:
    if not target_entities:
        return relationships
    return [
        relationship
        for relationship in relationships
        if normalize_name(relationship.source_name) in target_entities
        or normalize_name(relationship.target_name) in target_entities
    ]


def collect_entity_evidence_chunks(
    graph_query: ClinicalGraphQueryService,
    patient_id: str,
    target_entities: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    chunks = []
    for entity in target_entities:
        chunks.extend(
            {
                "entity": entity,
                **format_evidence_chunk(chunk),
            }
            for chunk in graph_query.get_evidence_chunks_for_entity(patient_id, entity)[:limit]
        )
    return chunks[:limit]


def collect_entity_paths(
    graph_query: ClinicalGraphQueryService,
    patient_id: str,
    target_entities: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    paths = []
    for source, target in combinations(target_entities, 2):
        paths.extend(
            {
                "source_entity": source,
                "target_entity": target,
                "steps": [format_entity_path_step(step) for step in path],
            }
            for path in graph_query.get_paths_between_entities(patient_id, source, target)
        )
    return paths[:limit]


def collect_entity_connected_events(
    graph_query: ClinicalGraphQueryService,
    patient_id: str,
    target_entities: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    events = []
    for entity in target_entities:
        events.extend(
            {
                "entity": entity,
                **format_medication_related_event(event),
            }
            for event in graph_query.get_events_related_to_medication(patient_id, entity)[:limit]
        )
    return events[:limit]


def parse_graph_date_range(date_range: Any) -> tuple[date, date] | None:
    if not isinstance(date_range, dict):
        return None

    start = parse_date(date_range.get("start"))
    end = parse_date(date_range.get("end"))
    if start is None or end is None:
        return None
    return start, end


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.fromisoformat(value).date()


def format_graph_entity(entity: GraphEntity) -> dict[str, Any]:
    return {
        "label": entity.label,
        "normalized_name": entity.normalized_name,
        "name": entity.name,
        "mention_count": entity.mention_count,
        "evidence_count": entity.evidence_count,
        "latest_seen_at": entity.latest_seen_at,
    }


def format_graph_relationship(relationship: GraphRelationship) -> dict[str, Any]:
    return {
        "source_label": relationship.source_label,
        "source_name": relationship.source_name,
        "relationship_type": relationship.relationship_type,
        "target_label": relationship.target_label,
        "target_name": relationship.target_name,
        "evidence": relationship.evidence,
        "confidence": relationship.confidence,
        "source_chunk_id": relationship.source_chunk_id,
    }


def format_evidence_chunk(chunk: EvidenceChunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "evidence": chunk.evidence,
        "confidence": chunk.confidence,
        "filename": chunk.filename,
        "created_at": chunk.created_at,
    }


def format_medication_related_event(event: MedicationRelatedEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "title": event.title,
        "occurred_at": event.occurred_at,
        "relationship_type": event.relationship_type,
        "confidence": event.confidence,
    }


def format_symptom_near_date(symptom: SymptomNearDate) -> dict[str, Any]:
    return {
        "normalized_name": symptom.normalized_name,
        "name": symptom.name,
        "chunk_id": symptom.chunk_id,
        "document_id": symptom.document_id,
        "created_at": symptom.created_at,
        "evidence": symptom.evidence,
        "confidence": symptom.confidence,
    }


def format_entity_path_step(step: EntityPathStep) -> dict[str, Any]:
    return {
        "source": step.source,
        "relationship_type": step.relationship_type,
        "relationship": step.relationship,
        "target": step.target,
    }


def normalize_name(value: str) -> str:
    return " ".join(value.split()).lower()


def _append_error(state: ClinicalAgentState, message: str) -> ClinicalAgentState:
    next_state = state.copy()
    next_state["errors"] = [*state.get("errors", []), message]
    return next_state
