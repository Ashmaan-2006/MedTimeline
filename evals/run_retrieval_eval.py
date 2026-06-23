from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def prediction_key(row: dict[str, Any]) -> tuple[str, str]:
    return row["patient_id"], row["question"]


def load_predictions(path: Path) -> dict[tuple[str, str], list[str]]:
    predictions = {}
    for row in load_jsonl(path):
        retrieved_chunk_ids = row.get("retrieved_chunk_ids", row.get("chunk_ids", []))
        predictions[prediction_key(row)] = [
            chunk_id
            for chunk_id in retrieved_chunk_ids
            if isinstance(chunk_id, str) and chunk_id.strip()
        ]
    return predictions


def recall_at_k(expected_chunk_ids: list[str], retrieved_chunk_ids: list[str], k: int) -> float:
    if not expected_chunk_ids:
        return 0.0
    expected = set(expected_chunk_ids)
    retrieved = set(retrieved_chunk_ids[:k])
    return len(expected & retrieved) / len(expected)


def precision_at_k(expected_chunk_ids: list[str], retrieved_chunk_ids: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    expected = set(expected_chunk_ids)
    retrieved = retrieved_chunk_ids[:k]
    return sum(chunk_id in expected for chunk_id in retrieved) / k


def reciprocal_rank(expected_chunk_ids: list[str], retrieved_chunk_ids: list[str]) -> float:
    expected = set(expected_chunk_ids)
    for index, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in expected:
            return 1 / index
    return 0.0


def missing_expected_chunks(
    expected_chunk_ids: list[str],
    retrieved_chunk_ids: list[str],
    k: int,
) -> list[str]:
    retrieved = set(retrieved_chunk_ids[:k])
    return [chunk_id for chunk_id in expected_chunk_ids if chunk_id not in retrieved]


def evaluate_retrieval(
    examples: list[dict[str, Any]],
    predictions: dict[tuple[str, str], list[str]],
) -> dict[str, Any]:
    if not examples:
        return {
            "example_count": 0,
            "recall_at_3": 0.0,
            "recall_at_5": 0.0,
            "precision_at_5": 0.0,
            "mrr": 0.0,
            "missing_expected_chunks": [],
        }

    per_example = []
    all_missing = []
    for example in examples:
        expected_chunk_ids = list(example.get("expected_chunk_ids", []))
        retrieved_chunk_ids = predictions.get(prediction_key(example), [])
        missing = missing_expected_chunks(expected_chunk_ids, retrieved_chunk_ids, k=5)
        all_missing.extend(
            {
                "patient_id": example["patient_id"],
                "question": example["question"],
                "chunk_id": chunk_id,
            }
            for chunk_id in missing
        )
        per_example.append(
            {
                "patient_id": example["patient_id"],
                "question": example["question"],
                "recall_at_3": recall_at_k(expected_chunk_ids, retrieved_chunk_ids, k=3),
                "recall_at_5": recall_at_k(expected_chunk_ids, retrieved_chunk_ids, k=5),
                "precision_at_5": precision_at_k(expected_chunk_ids, retrieved_chunk_ids, k=5),
                "mrr": reciprocal_rank(expected_chunk_ids, retrieved_chunk_ids),
                "missing_expected_chunks": missing,
            }
        )

    return {
        "example_count": len(examples),
        "recall_at_3": average(metric["recall_at_3"] for metric in per_example),
        "recall_at_5": average(metric["recall_at_5"] for metric in per_example),
        "precision_at_5": average(metric["precision_at_5"] for metric in per_example),
        "mrr": average(metric["mrr"] for metric in per_example),
        "missing_expected_chunks": all_missing,
        "per_example": per_example,
    }


def average(values: Any) -> float:
    values = list(values)
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def write_json(payload: dict[str, Any], output_path: Path | None) -> None:
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if output_path is None:
        print(serialized)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(serialized + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate MedGraph retrieval predictions.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/datasets/rag_questions.jsonl"),
        help="JSONL dataset containing expected_chunk_ids.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="JSONL predictions with patient_id, question, and retrieved_chunk_ids.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path. Defaults to stdout.",
    )
    args = parser.parse_args()

    examples = load_jsonl(args.dataset)
    predictions = load_predictions(args.predictions)
    write_json(evaluate_retrieval(examples, predictions), args.output)


if __name__ == "__main__":
    main()
