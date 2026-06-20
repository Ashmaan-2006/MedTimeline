from medgraph_api.agents.nodes.contradiction_checker import (
    ContradictionCheckingNode,
    claims_conflict,
    detect_contradictions,
    extract_claims_from_text,
    check_contradictions_node,
)
from medgraph_api.agents.state import create_initial_clinical_agent_state


def test_contradiction_checker_detects_symptom_conflict_from_vector_chunks() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Is chest pain consistent?")
    state["vector_context"] = [
        {
            "chunk_id": "chunk_123",
            "content": "Patient denied chest pain during the visit.",
            "source_snippet": "Patient denied chest pain during the visit.",
        },
        {
            "chunk_id": "chunk_456",
            "content": "Patient reported chest pain radiating to the arm.",
            "source_snippet": "Patient reported chest pain radiating to the arm.",
        },
    ]

    next_state = check_contradictions_node(state)

    assert next_state["contradictions"] == [
        {
            "claim_a": "Patient denied chest pain during the visit.",
            "claim_b": "Patient reported chest pain radiating to the arm.",
            "evidence_a": "chunk_123",
            "evidence_b": "chunk_456",
            "category": "symptom",
            "subject": "chest pain",
            "severity": "medium",
            "source_a": "vector_context",
            "source_b": "vector_context",
        }
    ]


def test_contradiction_checker_detects_medication_conflict_from_graph_context() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Was metoprolol stopped?")
    state["graph_context"] = [
        {
            "type": "entity_evidence_chunks",
            "items": [
                {
                    "chunk_id": "chunk_a",
                    "content": "Metoprolol was discontinued after dizziness.",
                },
                {
                    "chunk_id": "chunk_b",
                    "content": "Metoprolol continued on the discharge medication list.",
                },
            ],
        }
    ]

    next_state = ContradictionCheckingNode()(state)

    assert next_state["contradictions"][0]["subject"] == "metoprolol"
    assert next_state["contradictions"][0]["evidence_a"] == "chunk_a"
    assert next_state["contradictions"][0]["evidence_b"] == "chunk_b"
    assert next_state["contradictions"][0]["severity"] == "low"


def test_contradiction_checker_detects_troponin_conflict_as_high_severity() -> None:
    claims = [
        *extract_claims_from_text("Troponin was normal.", "chunk_1", "test"),
        *extract_claims_from_text("Troponin elevated on repeat lab report.", "chunk_2", "test"),
    ]

    contradictions = detect_contradictions(claims)

    assert contradictions[0]["subject"] == "troponin"
    assert contradictions[0]["severity"] == "high"


def test_extract_claims_from_text_marks_denied_symptom_absent() -> None:
    claims = extract_claims_from_text(
        "Patient denies shortness of breath.",
        evidence_id="chunk_1",
        source="test",
    )

    assert claims[0].category == "symptom"
    assert claims[0].subject == "shortness of breath"
    assert claims[0].status == "absent"


def test_claims_conflict_ignores_same_evidence_id() -> None:
    absent, present = [
        *extract_claims_from_text("Patient denied chest pain.", "chunk_1", "test"),
        *extract_claims_from_text("Patient reported chest pain.", "chunk_1", "test"),
    ]

    assert claims_conflict(absent, present) is False


def test_contradiction_checker_preserves_empty_result_when_no_conflicts_exist() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Any conflicts?")
    state["vector_context"] = [
        {
            "chunk_id": "chunk_1",
            "content": "Patient denied chest pain.",
        }
    ]

    next_state = check_contradictions_node(state)

    assert next_state["contradictions"] == []
