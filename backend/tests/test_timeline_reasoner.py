from medgraph_api.agents.nodes.timeline_reasoner import (
    TimelineReasoningNode,
    collect_timeline_events,
    extract_date_from_text,
    format_ordered_timeline,
    parse_temporal_value,
    reason_over_timeline_node,
)
from medgraph_api.agents.state import create_initial_clinical_agent_state


def test_timeline_reasoning_node_orders_relevant_evidence_chronologically() -> None:
    state = create_initial_clinical_agent_state(
        patient_id="patient-1",
        user_question="Did symptoms worsen after metoprolol?",
    )
    state["vector_context"] = [
        {
            "chunk_id": "chunk-3",
            "document_id": "document-1",
            "content": "2026-03-10: Patient reported worsening shortness of breath.",
            "source_snippet": "Patient reported worsening shortness of breath.",
            "similarity_score": 0.91,
            "created_at": "2026-03-10T09:00:00+00:00",
        },
        {
            "chunk_id": "chunk-1",
            "document_id": "document-1",
            "content": "2026-03-04: Patient reported dizziness.",
            "source_snippet": "Patient reported dizziness.",
            "similarity_score": 0.88,
            "created_at": "2026-03-04T09:00:00+00:00",
        },
    ]
    state["graph_context"] = [
        {
            "type": "entity_connected_events",
            "items": [
                {
                    "event_id": "event-2",
                    "entity": "metoprolol",
                    "title": "Metoprolol dose increased.",
                    "occurred_at": "2026-03-07",
                    "relationship_type": "STARTED_AT",
                    "confidence": 0.84,
                }
            ],
        }
    ]

    next_state = reason_over_timeline_node(state)

    assert [event["narrative"] for event in next_state["timeline_context"]] == [
        "1. March 4: Patient reported dizziness.",
        "2. March 7: Metoprolol dose increased.",
        "3. March 10: Patient reported worsening shortness of breath.",
    ]


def test_timeline_reasoning_node_can_be_used_as_callable_node() -> None:
    state = create_initial_clinical_agent_state("patient-1", "What happened?")
    state["vector_context"] = [
        {
            "chunk_id": "chunk-1",
            "content": "2026-01-05: Patient reports chest pain.",
            "created_at": "2026-01-05T12:00:00+00:00",
        }
    ]

    next_state = TimelineReasoningNode()(state)

    assert next_state["timeline_context"][0]["display_date"] == "January 5"


def test_collect_timeline_events_extracts_graph_relationship_and_symptom_dates() -> None:
    graph_context = [
        {
            "type": "relationships",
            "items": [
                {
                    "source_name": "shortness of breath",
                    "relationship_type": "WORSENED_AFTER",
                    "target_name": "March 10 event",
                    "evidence": "Shortness of breath worsened after dose change.",
                    "confidence": 0.8,
                    "source_chunk_id": "chunk-2",
                }
            ],
        },
        {
            "type": "symptoms_near_date",
            "items": [
                {
                    "normalized_name": "dizziness",
                    "created_at": "2026-03-04T00:00:00+00:00",
                    "evidence": "Patient reported dizziness.",
                    "chunk_id": "chunk-1",
                    "document_id": "document-1",
                    "confidence": 0.76,
                }
            ],
        },
    ]

    events = collect_timeline_events(vector_context=[], graph_context=graph_context)
    timeline = format_ordered_timeline(events)

    assert [event["display_date"] for event in timeline] == ["March 4", "March 10"]
    assert timeline[1]["summary"] == "Shortness of breath worsened after dose change."


def test_parse_temporal_value_supports_iso_and_month_day_values() -> None:
    assert parse_temporal_value("2026-03-04T12:00:00+00:00").isoformat() == (
        "2026-03-04T12:00:00+00:00"
    )
    assert parse_temporal_value("March 7, 2026").date().isoformat() == "2026-03-07"


def test_extract_date_from_text_finds_iso_or_month_date() -> None:
    assert extract_date_from_text("Patient seen on 2026-03-04.") == "2026-03-04"
    assert extract_date_from_text("Patient seen on March 10.") == "March 10"
