import re
from datetime import UTC, date, datetime, time
from typing import Any

from medgraph_api.agents.state import ClinicalAgentState


class TimelineReasoningNode:
    def __call__(self, state: ClinicalAgentState) -> ClinicalAgentState:
        return reason_over_timeline_node(state)


def reason_over_timeline_node(state: ClinicalAgentState) -> ClinicalAgentState:
    timeline_events = collect_timeline_events(
        vector_context=state.get("vector_context", []),
        graph_context=state.get("graph_context", []),
    )

    next_state = state.copy()
    next_state["timeline_context"] = format_ordered_timeline(timeline_events)
    return next_state


def collect_timeline_events(
    vector_context: list[dict[str, Any]],
    graph_context: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events = []
    events.extend(extract_vector_timeline_events(vector_context))
    events.extend(extract_graph_timeline_events(graph_context))
    return deduplicate_timeline_events(events)


def extract_vector_timeline_events(vector_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for chunk in vector_context:
        occurred_at = parse_temporal_value(
            chunk.get("occurred_at")
            or chunk.get("event_date")
            or nested_get(chunk, ["chunk_metadata", "occurred_at"])
            or nested_get(chunk, ["chunk_metadata", "event_date"])
            or extract_date_from_text(chunk.get("content", ""))
            or chunk.get("created_at")
        )
        if occurred_at is None:
            continue

        events.append(
            {
                "occurred_at": occurred_at,
                "summary": summarize_evidence_text(
                    chunk.get("source_snippet") or chunk.get("content") or "Relevant document chunk."
                ),
                "source": "vector",
                "document_id": chunk.get("document_id"),
                "chunk_id": chunk.get("chunk_id"),
                "confidence": chunk.get("similarity_score"),
                "evidence": chunk.get("source_snippet") or chunk.get("content"),
            }
        )
    return events


def extract_graph_timeline_events(graph_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for section in graph_context:
        section_type = section.get("type")
        items = section.get("items", [])
        if section_type == "relationships":
            events.extend(extract_relationship_events(items))
        elif section_type == "entity_connected_events":
            events.extend(extract_connected_events(items))
        elif section_type == "symptoms_near_date":
            events.extend(extract_symptom_events(items))
        elif section_type == "entity_evidence_chunks":
            events.extend(extract_evidence_chunk_events(items))
    return events


def extract_relationship_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for relationship in items:
        occurred_at = parse_temporal_value(
            relationship.get("occurred_at")
            or relationship.get("event_date")
            or extract_date_from_text(relationship.get("target_name", ""))
            or extract_date_from_text(relationship.get("evidence", ""))
        )
        if occurred_at is None:
            continue

        events.append(
            {
                "occurred_at": occurred_at,
                "summary": build_relationship_summary(relationship),
                "source": "graph_relationship",
                "chunk_id": relationship.get("source_chunk_id"),
                "confidence": relationship.get("confidence"),
                "evidence": relationship.get("evidence"),
            }
        )
    return events


def extract_connected_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for item in items:
        occurred_at = parse_temporal_value(item.get("occurred_at"))
        if occurred_at is None:
            continue

        events.append(
            {
                "occurred_at": occurred_at,
                "summary": item.get("title") or build_connected_event_summary(item),
                "source": "graph_event",
                "event_id": item.get("event_id"),
                "entity": item.get("entity"),
                "confidence": item.get("confidence"),
                "evidence": item.get("relationship_type"),
            }
        )
    return events


def extract_symptom_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for symptom in items:
        occurred_at = parse_temporal_value(symptom.get("created_at"))
        if occurred_at is None:
            continue

        symptom_name = symptom.get("name") or symptom.get("normalized_name") or "Symptom"
        evidence = symptom.get("evidence")
        events.append(
            {
                "occurred_at": occurred_at,
                "summary": evidence or f"{symptom_name} mentioned.",
                "source": "graph_symptom",
                "document_id": symptom.get("document_id"),
                "chunk_id": symptom.get("chunk_id"),
                "confidence": symptom.get("confidence"),
                "evidence": evidence,
            }
        )
    return events


def extract_evidence_chunk_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for chunk in items:
        occurred_at = parse_temporal_value(
            chunk.get("occurred_at")
            or chunk.get("event_date")
            or extract_date_from_text(chunk.get("content", ""))
            or chunk.get("created_at")
        )
        if occurred_at is None:
            continue

        events.append(
            {
                "occurred_at": occurred_at,
                "summary": summarize_evidence_text(
                    chunk.get("evidence") or chunk.get("content") or "Graph evidence chunk."
                ),
                "source": "graph_evidence_chunk",
                "document_id": chunk.get("document_id"),
                "chunk_id": chunk.get("chunk_id"),
                "entity": chunk.get("entity"),
                "confidence": chunk.get("confidence"),
                "evidence": chunk.get("evidence") or chunk.get("content"),
            }
        )
    return events


def format_ordered_timeline(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered_events = sorted(events, key=lambda event: event["occurred_at"])
    return [
        {
            **{key: value for key, value in event.items() if key != "occurred_at"},
            "occurred_at": event["occurred_at"].isoformat(),
            "display_date": format_display_date(event["occurred_at"]),
            "sequence": index,
            "narrative": f"{index}. {format_display_date(event['occurred_at'])}: {event['summary']}",
        }
        for index, event in enumerate(ordered_events, start=1)
    ]


def deduplicate_timeline_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduplicated_events = []
    seen_keys = set()
    for event in events:
        key = (
            event["occurred_at"].date().isoformat(),
            normalize_text(event.get("summary", "")),
            event.get("chunk_id"),
            event.get("event_id"),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduplicated_events.append(event)
    return deduplicated_events


def parse_temporal_value(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None

    normalized_value = value.strip()
    try:
        parsed_value = datetime.fromisoformat(normalized_value.replace("Z", "+00:00"))
    except ValueError:
        parsed_date = parse_month_day_year(normalized_value)
        if parsed_date is None:
            return None
        return datetime.combine(parsed_date, time.min, tzinfo=UTC)

    return parsed_value if parsed_value.tzinfo is not None else parsed_value.replace(tzinfo=UTC)


def parse_month_day_year(text: str) -> date | None:
    match = re.search(
        r"\b("
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
        r")\s+(\d{1,2})(?:,\s*(\d{4}))?\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    month_name, day_text, year_text = match.groups()
    month_number = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }[month_name[:3].lower()]
    return date(int(year_text or datetime.now(UTC).year), month_number, int(day_text))


def extract_date_from_text(text: str) -> str | None:
    iso_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if iso_match:
        return iso_match.group(0)

    month_match = re.search(
        r"\b("
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
        r")\s+\d{1,2}(?:,\s*\d{4})?\b",
        text,
        flags=re.IGNORECASE,
    )
    if month_match:
        return month_match.group(0)
    return None


def build_relationship_summary(relationship: dict[str, Any]) -> str:
    relationship_type = str(relationship.get("relationship_type", "related to")).lower()
    relationship_text = relationship_type.replace("_", " ")
    source_name = relationship.get("source_name") or "Entity"
    target_name = relationship.get("target_name") or "event"
    evidence = relationship.get("evidence")
    if evidence:
        return summarize_evidence_text(str(evidence))
    return f"{source_name} {relationship_text} {target_name}."


def build_connected_event_summary(item: dict[str, Any]) -> str:
    entity = item.get("entity") or "Entity"
    relationship_type = str(item.get("relationship_type", "connected")).lower().replace("_", " ")
    return f"{entity} {relationship_type}."


def summarize_evidence_text(text: str, max_length: int = 180) -> str:
    normalized = " ".join(text.split()).strip()
    if not normalized:
        return "Evidence mentioned."
    if len(normalized) <= max_length:
        return ensure_terminal_punctuation(normalized)

    truncated = normalized[: max_length - 3].rstrip()
    word_boundary = truncated.rfind(" ")
    if word_boundary > 0:
        truncated = truncated[:word_boundary]
    return ensure_terminal_punctuation(truncated + "...")


def ensure_terminal_punctuation(text: str) -> str:
    if text.endswith((".", "?", "!", "...")):
        return text
    return text + "."


def format_display_date(value: datetime) -> str:
    return f"{value.strftime('%B')} {value.day}"


def nested_get(payload: dict[str, Any], keys: list[str]) -> Any:
    current_value: Any = payload
    for key in keys:
        if not isinstance(current_value, dict):
            return None
        current_value = current_value.get(key)
    return current_value


def normalize_text(value: str) -> str:
    return " ".join(value.split()).lower()
