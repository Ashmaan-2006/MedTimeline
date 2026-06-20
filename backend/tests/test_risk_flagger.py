from medgraph_api.agents.nodes.risk_flagger import (
    RISK_DISCLAIMER,
    ClinicalRiskFlaggingNode,
    detect_risk_flags,
    flag_clinical_risks_node,
)
from medgraph_api.agents.state import create_initial_clinical_agent_state


def test_risk_flagger_detects_worsening_symptoms_and_abnormal_labs() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Any risk signals?")
    state["vector_context"] = [
        {
            "chunk_id": "chunk_1",
            "source_snippet": "Patient reported worsening shortness of breath.",
        },
        {
            "chunk_id": "chunk_2",
            "source_snippet": "Troponin elevated on repeat lab report.",
        },
    ]

    next_state = flag_clinical_risks_node(state)

    assert [flag["category"] for flag in next_state["risk_flags"]] == [
        "worsening_symptoms",
        "abnormal_lab",
    ]
    assert next_state["risk_flags"][0]["disclaimer"] == RISK_DISCLAIMER
    assert next_state["risk_flags"][1]["severity"] == "high"


def test_risk_flagger_detects_medication_discontinuity_and_missing_follow_up() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Any follow-up concerns?")
    state["graph_context"] = [
        {
            "type": "entity_evidence_chunks",
            "items": [
                {
                    "chunk_id": "chunk_3",
                    "content": "Metoprolol was discontinued after dizziness.",
                },
                {
                    "chunk_id": "chunk_4",
                    "content": "No follow-up was documented after discharge.",
                },
            ],
        }
    ]

    next_state = ClinicalRiskFlaggingNode()(state)

    assert [flag["category"] for flag in next_state["risk_flags"]] == [
        "medication_discontinuity",
        "missing_follow_up",
    ]
    assert next_state["risk_flags"][0]["evidence_ids"] == ["chunk_3"]
    assert next_state["risk_flags"][1]["evidence_ids"] == ["chunk_4"]


def test_risk_flagger_detects_repeated_emergency_visits() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Any utilization concerns?")
    state["timeline_context"] = [
        {"chunk_id": "chunk_1", "summary": "ED visit for chest pain."},
        {"chunk_id": "chunk_2", "summary": "Returned to emergency department two days later."},
    ]

    risk_flags = detect_risk_flags(state)

    assert risk_flags == [
        {
            "category": "repeated_emergency_visits",
            "title": "Repeated emergency care mentions",
            "rationale": "Multiple evidence items mention emergency or ED visits.",
            "severity": "medium",
            "evidence_ids": ["chunk_1", "chunk_2"],
            "source": "timeline_context",
            "disclaimer": RISK_DISCLAIMER,
        }
    ]


def test_risk_flagger_surfaces_conflicting_records_as_review_flag() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Any documentation concerns?")
    state["contradictions"] = [
        {
            "subject": "chest pain",
            "severity": "medium",
            "evidence_a": "chunk_a",
            "evidence_b": "chunk_b",
        }
    ]

    risk_flags = detect_risk_flags(state)

    assert risk_flags == [
        {
            "category": "conflicting_records",
            "title": "Conflicting record evidence",
            "rationale": (
                "Contradiction detection found conflicting documentation for chest pain."
            ),
            "severity": "medium",
            "evidence_ids": ["chunk_a", "chunk_b"],
            "source": "contradictions",
            "disclaimer": RISK_DISCLAIMER,
        }
    ]


def test_risk_flagger_returns_empty_flags_when_no_signals_exist() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Any risk signals?")
    state["vector_context"] = [{"chunk_id": "chunk_1", "source_snippet": "Routine visit."}]

    next_state = flag_clinical_risks_node(state)

    assert next_state["risk_flags"] == []
