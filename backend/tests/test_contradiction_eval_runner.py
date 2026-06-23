import json
from pathlib import Path

from evals.run_contradiction_eval import (
    evaluate_contradictions,
    expected_contradictions,
    load_contradiction_predictions,
    score_contradiction_example,
)


def test_score_contradiction_example_counts_true_positive_and_evidence_quality() -> None:
    example = {
        "patient_id": "patient-1",
        "question": "Are there contradictions about chest pain?",
        "expected_contradictions": [
            {
                "subject": "chest pain",
                "category": "symptom",
                "claim_a": "Patient denies chest pain.",
                "claim_b": "Patient reports chest pain.",
                "evidence_chunk_ids": ["chunk-a", "chunk-b"],
            }
        ],
    }
    prediction = {
        "contradictions": [
            {
                "subject": "chest pain",
                "category": "symptom",
                "claim_a": "Patient denied chest pain.",
                "claim_b": "Patient reported chest pain.",
                "evidence_a": "chunk-a",
                "evidence_b": "chunk-b",
            }
        ]
    }

    score = score_contradiction_example(example, prediction)

    assert score["true_positives"] == 1
    assert score["false_positives"] == 0
    assert score["false_negatives"] == 0
    assert score["precision"] == 1.0
    assert score["recall"] == 1.0
    assert score["contradiction_evidence_quality"] == 1.0


def test_score_contradiction_example_counts_false_positive_and_false_negative() -> None:
    example = {
        "patient_id": "patient-1",
        "question": "Are medications consistent?",
        "expected_contradictions": [
            {
                "subject": "metoprolol",
                "category": "medication",
                "evidence_chunk_ids": ["chunk-1", "chunk-2"],
            }
        ],
    }
    prediction = {
        "contradictions": [
            {
                "subject": "troponin",
                "category": "lab",
                "evidence_a": "chunk-9",
                "evidence_b": "chunk-10",
            }
        ]
    }

    score = score_contradiction_example(example, prediction)

    assert score["true_positives"] == 0
    assert score["false_positives"] == 1
    assert score["false_negatives"] == 1
    assert score["missing_contradictions"] == ["metoprolol"]
    assert score["extra_contradictions"] == ["troponin"]


def test_expected_contradictions_can_be_inferred_from_existing_dataset_shape() -> None:
    example = {
        "expected_entities": ["chest pain"],
        "expected_relationships": ["CONTRAINDICATES"],
        "expected_chunk_ids": ["chunk_52", "chunk_58"],
    }

    expected = expected_contradictions(example)

    assert expected == [
        {
            "subject": "chest pain",
            "category": None,
            "claim_a": None,
            "claim_b": None,
            "evidence_chunk_ids": {"chunk_52", "chunk_58"},
        }
    ]


def test_evaluate_contradictions_returns_aggregate_metrics() -> None:
    examples = [
        {
            "patient_id": "patient-1",
            "question": "Question one?",
            "expected_contradictions": [
                {"subject": "chest pain", "evidence_chunk_ids": ["chunk-a", "chunk-b"]}
            ],
        },
        {
            "patient_id": "patient-2",
            "question": "Question two?",
            "expected_contradictions": [
                {"subject": "troponin", "evidence_chunk_ids": ["chunk-c", "chunk-d"]}
            ],
        },
    ]
    predictions = {
        ("patient-1", "Question one?"): {
            "contradictions": [
                {
                    "subject": "chest pain",
                    "evidence_a": "chunk-a",
                    "evidence_b": "chunk-b",
                }
            ]
        },
        ("patient-2", "Question two?"): {"contradictions": []},
    }

    metrics = evaluate_contradictions(examples, predictions)

    assert metrics["true_positives"] == 1
    assert metrics["false_positives"] == 0
    assert metrics["false_negatives"] == 1
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.6667
    assert metrics["contradiction_evidence_quality"] == 0.5


def test_load_contradiction_predictions_keys_rows_by_patient_and_question(
    tmp_path: Path,
) -> None:
    predictions_path = tmp_path / "contradictions.jsonl"
    predictions_path.write_text(
        json.dumps(
            {
                "patient_id": "patient-1",
                "question": "Question?",
                "contradictions": [{"subject": "chest pain"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    predictions = load_contradiction_predictions(predictions_path)

    assert predictions[("patient-1", "Question?")]["contradictions"] == [
        {"subject": "chest pain"}
    ]
