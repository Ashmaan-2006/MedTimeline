import json

from evals.run_graph_eval import (
    evaluate_graph_retrieval,
    extract_evidence_chunk_ids,
    extract_relationship_types,
    load_graph_predictions,
    path_is_relevant,
)


def test_graph_eval_scores_expected_entities_relationships_paths_and_evidence() -> None:
    examples = [
        {
            "patient_id": "patient-1",
            "question": "Did dizziness worsen after metoprolol?",
            "expected_entities": ["metoprolol", "dizziness"],
            "expected_relationships": ["WORSENED_AFTER"],
            "expected_chunk_ids": ["chunk-1", "chunk-2"],
        },
        {
            "patient_id": "patient-2",
            "question": "Was troponin elevated?",
            "expected_entities": ["troponin"],
            "expected_relationships": ["EVIDENCED_BY"],
            "expected_chunk_ids": ["chunk-9"],
        },
    ]
    predictions = {
        (
            "patient-1",
            "Did dizziness worsen after metoprolol?",
        ): {
            "retrieved_entities": [
                {"normalized_name": "metoprolol", "source_chunk_id": "chunk-1"},
                "dizziness",
            ],
            "retrieved_relationships": [
                {
                    "relationship_type": "WORSENED_AFTER",
                    "source": "metoprolol",
                    "target": "dizziness",
                    "evidence_chunk_ids": ["chunk-2"],
                }
            ],
            "retrieved_paths": [
                {
                    "entities": ["metoprolol", "dizziness"],
                    "relationships": ["WORSENED_AFTER"],
                }
            ],
        },
        ("patient-2", "Was troponin elevated?"): {
            "retrieved_entities": [],
            "retrieved_relationships": [],
            "retrieved_paths": [],
        },
    }

    metrics = evaluate_graph_retrieval(examples, predictions)

    assert metrics["example_count"] == 2
    assert metrics["entity_recall"] == 0.5
    assert metrics["relationship_recall"] == 0.5
    assert metrics["path_relevance"] == 0.5
    assert metrics["evidence_chunk_linkage"] == 0.5
    assert metrics["per_example"][1]["missing_entities"] == ["troponin"]
    assert metrics["per_example"][1]["missing_relationships"] == ["EVIDENCED_BY"]
    assert metrics["per_example"][1]["missing_evidence_chunk_ids"] == ["chunk-9"]


def test_graph_eval_extracts_relationship_and_evidence_variants() -> None:
    prediction = {
        "retrieved_relationships": [
            "temporally associated with",
            {"type": "WORSENED-AFTER", "source_chunk_id": "chunk-a"},
            {"relationship_type": "evidenced_by", "chunk_id": "chunk-b"},
        ],
        "retrieved_entities": [{"name": "Dizziness", "evidence_chunk_ids": ["chunk-c"]}],
        "evidence_chunk_links": [{"chunk_id": "chunk-d"}, "chunk-e"],
    }

    assert extract_relationship_types(prediction) == {
        "TEMPORALLY_ASSOCIATED_WITH",
        "WORSENED_AFTER",
        "EVIDENCED_BY",
    }
    assert extract_evidence_chunk_ids(prediction) == {
        "chunk-a",
        "chunk-b",
        "chunk-c",
        "chunk-d",
        "chunk-e",
    }


def test_path_relevance_accepts_step_based_paths() -> None:
    prediction = {
        "retrieved_paths": [
            {
                "steps": [
                    {
                        "source": "metoprolol",
                        "relationship_type": "TEMPORALLY_ASSOCIATED_WITH",
                        "target": "dizziness",
                    }
                ]
            }
        ]
    }

    assert path_is_relevant(
        expected_entities={"metoprolol", "dizziness"},
        expected_relationships={"WORSENED_AFTER"},
        prediction=prediction,
    )


def test_load_graph_predictions_keys_rows_by_patient_and_question(tmp_path) -> None:
    predictions_path = tmp_path / "graph_predictions.jsonl"
    rows = [
        {
            "patient_id": "patient-1",
            "question": "Question?",
            "retrieved_entities": ["metoprolol"],
        }
    ]
    predictions_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    predictions = load_graph_predictions(predictions_path)

    assert predictions[("patient-1", "Question?")]["retrieved_entities"] == [
        "metoprolol"
    ]
