from medgraph_api.agents.nodes.answer_generator import (
    GroundedAnswerGenerationNode,
    estimate_confidence,
    generate_grounded_answer_node,
    generate_grounded_clinical_answer,
)
from medgraph_api.agents.nodes.risk_flagger import RISK_DISCLAIMER
from medgraph_api.agents.state import create_initial_clinical_agent_state


def test_grounded_answer_generator_uses_only_retrieved_context_with_citations() -> None:
    state = create_initial_clinical_agent_state(
        "patient-1",
        "Did symptoms worsen after metoprolol?",
    )
    state["timeline_context"] = [
        {
            "display_date": "March 7",
            "summary": "Metoprolol dose increased.",
            "chunk_id": "chunk_1",
        },
        {
            "display_date": "March 10",
            "summary": "Patient reported worsening shortness of breath.",
            "chunk_id": "chunk_2",
        },
    ]
    state["graph_context"] = [
        {
            "type": "relationships",
            "items": [
                {
                    "source_name": "shortness of breath",
                    "relationship_type": "WORSENED_AFTER",
                    "target_name": "metoprolol dose increase",
                    "evidence": "shortness of breath worsened after metoprolol change",
                    "source_chunk_id": "chunk_2",
                }
            ],
        }
    ]
    state["risk_flags"] = [
        {
            "title": "Worsening symptom signal",
            "rationale": "Evidence mentions symptoms worsening or clinical deterioration.",
            "evidence_ids": ["chunk_2"],
        }
    ]

    answer = generate_grounded_clinical_answer(state)

    assert "March 7: Metoprolol dose increased. [1]" in answer["answer"]
    assert "Graph evidence links shortness of breath worsened after metoprolol dose increase [2]." in (
        answer["answer"]
    )
    assert "not a diagnosis" in answer["answer"]
    assert RISK_DISCLAIMER in answer["answer"]
    assert answer["confidence"] == "medium"
    assert answer["citations"][0]["evidence_id"] == "chunk_1"
    assert answer["limitations"] == ["No lab report evidence was available in the retrieved context."]


def test_grounded_answer_node_writes_answer_fields_to_state() -> None:
    state = create_initial_clinical_agent_state("patient-1", "What happened?")
    state["vector_context"] = [
        {
            "chunk_id": "chunk_1",
            "document_id": "document_1",
            "source_snippet": "Patient reported dizziness.",
        }
    ]

    next_state = GroundedAnswerGenerationNode()(state)

    assert next_state["final_answer"].startswith("Retrieved document evidence states:")
    assert next_state["citations"] == [
        {
            "label": "[1]",
            "source_type": "vector_chunk",
            "evidence_id": "chunk_1",
            "document_id": "document_1",
            "snippet": "Patient reported dizziness.",
        }
    ]
    assert next_state["answer_confidence"] == "low"
    assert "No clinical graph relationship evidence was available." in next_state["limitations"]


def test_grounded_answer_generator_returns_insufficient_evidence_without_context() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Why did symptoms worsen?")

    answer = generate_grounded_clinical_answer(state)

    assert answer == {
        "answer": (
            "Insufficient evidence was retrieved to answer this question. "
            f"{RISK_DISCLAIMER}"
        ),
        "citations": [],
        "confidence": "low",
        "limitations": [
            "No vector, graph, timeline, contradiction, or risk evidence was available."
        ],
    }


def test_grounded_answer_generator_mentions_conflicting_records_as_limitation() -> None:
    state = create_initial_clinical_agent_state("patient-1", "Is chest pain consistent?")
    state["contradictions"] = [
        {
            "claim_a": "Patient denied chest pain",
            "claim_b": "Patient reported chest pain",
            "evidence_a": "chunk_a",
            "evidence_b": "chunk_b",
        }
    ]

    next_state = generate_grounded_answer_node(state)

    assert "conflicting documentation" in next_state["final_answer"]
    assert "Conflicting documentation lowers certainty" in next_state["limitations"][-1]
    assert next_state["answer_confidence"] == "low"


def test_estimate_confidence_uses_evidence_and_limitations() -> None:
    assert estimate_confidence([{}, {}, {}, {}], [], []) == "high"
    assert estimate_confidence([{}, {}], ["No graph evidence."], []) == "medium"
    assert estimate_confidence([{}], ["No graph evidence."], []) == "low"
