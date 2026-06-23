import json
from pathlib import Path

from evals.run_retrieval_eval import (
    evaluate_retrieval,
    load_jsonl,
    load_predictions,
    missing_expected_chunks,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_retrieval_metrics_for_single_example() -> None:
    expected = ["chunk_1", "chunk_2", "chunk_3"]
    retrieved = ["chunk_x", "chunk_2", "chunk_1", "chunk_y", "chunk_z"]

    assert recall_at_k(expected, retrieved, k=3) == 2 / 3
    assert recall_at_k(expected, retrieved, k=5) == 2 / 3
    assert precision_at_k(expected, retrieved, k=5) == 2 / 5
    assert reciprocal_rank(expected, retrieved) == 1 / 2
    assert missing_expected_chunks(expected, retrieved, k=5) == ["chunk_3"]


def test_evaluate_retrieval_returns_aggregate_metrics_and_missing_chunks() -> None:
    examples = [
        {
            "patient_id": "demo_patient_001",
            "question": "Question one?",
            "expected_chunk_ids": ["chunk_1", "chunk_2"],
        },
        {
            "patient_id": "demo_patient_002",
            "question": "Question two?",
            "expected_chunk_ids": ["chunk_9"],
        },
    ]
    predictions = {
        ("demo_patient_001", "Question one?"): ["chunk_2", "chunk_3", "chunk_4"],
        ("demo_patient_002", "Question two?"): ["chunk_a", "chunk_b", "chunk_9"],
    }

    result = evaluate_retrieval(examples, predictions)

    assert result["example_count"] == 2
    assert result["recall_at_3"] == 0.75
    assert result["recall_at_5"] == 0.75
    assert result["precision_at_5"] == 0.2
    assert result["mrr"] == 0.6667
    assert result["missing_expected_chunks"] == [
        {
            "patient_id": "demo_patient_001",
            "question": "Question one?",
            "chunk_id": "chunk_1",
        }
    ]


def test_load_predictions_accepts_retrieved_chunk_ids(tmp_path: Path) -> None:
    predictions_path = tmp_path / "predictions.jsonl"
    predictions_path.write_text(
        json.dumps(
            {
                "patient_id": "demo_patient_001",
                "question": "Question?",
                "retrieved_chunk_ids": ["chunk_1", "chunk_2"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert load_predictions(predictions_path) == {
        ("demo_patient_001", "Question?"): ["chunk_1", "chunk_2"]
    }


def test_load_jsonl_ignores_empty_lines(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text('{"patient_id": "demo"}\n\n', encoding="utf-8")

    assert load_jsonl(dataset_path) == [{"patient_id": "demo"}]
