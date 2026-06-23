"""Evaluate clinical contradiction detection outputs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]
PredictionKey = tuple[str, str]

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "patient",
    "record",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}") from exc
    return rows


def prediction_key(row: JsonObject) -> PredictionKey:
    return str(row["patient_id"]), str(row["question"])


def load_contradiction_predictions(path: Path) -> dict[PredictionKey, JsonObject]:
    return {prediction_key(row): row for row in load_jsonl(path)}


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def tokenize(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", normalize_text(value))
        if len(token) > 2 and token not in STOPWORDS
    }


def normalize_relationship(value: Any) -> str:
    text = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    return re.sub(r"_+", "_", text)


def normalize_chunk_id(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def extract_chunk_ids(value: Any) -> set[str]:
    chunk_ids: set[str] = set()

    def add(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, list):
            for nested in item:
                add(nested)
            return
        if isinstance(item, dict):
            for key in (
                "chunk_id",
                "chunk_ids",
                "evidence_chunk_id",
                "evidence_chunk_ids",
                "evidence_a",
                "evidence_b",
                "source_chunk_id",
            ):
                add(item.get(key))
            return
        normalized = normalize_chunk_id(item)
        if normalized:
            chunk_ids.add(normalized)

    add(value)
    return chunk_ids


def expected_contradictions(example: JsonObject) -> list[JsonObject]:
    explicit = example.get("expected_contradictions")
    if explicit:
        return [canonical_expected_contradiction(item) for item in explicit]

    expected_relationships = {
        normalize_relationship(item) for item in example.get("expected_relationships", [])
    }
    expected_chunk_ids = [
        chunk_id
        for chunk_id in example.get("expected_chunk_ids", [])
        if normalize_chunk_id(chunk_id)
    ]
    expected_entities = [
        normalize_text(entity)
        for entity in example.get("expected_entities", [])
        if normalize_text(entity)
    ]

    if "CONTRAINDICATES" not in expected_relationships:
        return []

    return [
        {
            "subject": expected_entities[0] if expected_entities else None,
            "category": None,
            "claim_a": None,
            "claim_b": None,
            "evidence_chunk_ids": set(expected_chunk_ids),
        }
    ]


def canonical_expected_contradiction(item: Any) -> JsonObject:
    if isinstance(item, str):
        return {
            "subject": normalize_text(item),
            "category": None,
            "claim_a": None,
            "claim_b": None,
            "evidence_chunk_ids": set(),
        }

    evidence_chunk_ids = extract_chunk_ids(item.get("evidence_chunk_ids") or item)
    return {
        "subject": normalize_text(item.get("subject") or item.get("entity")),
        "category": normalize_text(item.get("category")),
        "claim_a": item.get("claim_a"),
        "claim_b": item.get("claim_b"),
        "evidence_chunk_ids": evidence_chunk_ids,
    }


def predicted_contradictions(prediction: JsonObject) -> list[JsonObject]:
    raw_contradictions = (
        prediction.get("contradictions")
        or prediction.get("detected_contradictions")
        or prediction.get("possible_conflicts")
        or []
    )
    return [canonical_predicted_contradiction(item) for item in raw_contradictions]


def canonical_predicted_contradiction(item: Any) -> JsonObject:
    if isinstance(item, str):
        return {
            "subject": None,
            "category": None,
            "claim_a": item,
            "claim_b": None,
            "evidence_chunk_ids": set(),
        }

    return {
        "subject": normalize_text(item.get("subject") or item.get("entity")),
        "category": normalize_text(item.get("category")),
        "claim_a": item.get("claim_a"),
        "claim_b": item.get("claim_b"),
        "evidence_chunk_ids": extract_chunk_ids(item),
        "severity": item.get("severity"),
    }


def contradiction_match_score(expected: JsonObject, predicted: JsonObject) -> float:
    score = 0.0
    expected_subject = expected.get("subject")
    predicted_subject = predicted.get("subject")
    if expected_subject and predicted_subject and expected_subject == predicted_subject:
        score += 0.55

    expected_category = expected.get("category")
    predicted_category = predicted.get("category")
    if expected_category and predicted_category and expected_category == predicted_category:
        score += 0.15

    expected_chunks = set(expected.get("evidence_chunk_ids", set()))
    predicted_chunks = set(predicted.get("evidence_chunk_ids", set()))
    if expected_chunks:
        overlap_count = len(expected_chunks & predicted_chunks)
        score += min(0.3, 0.15 * overlap_count)

    expected_claim_tokens = tokenize(expected.get("claim_a")) | tokenize(expected.get("claim_b"))
    predicted_claim_tokens = tokenize(predicted.get("claim_a")) | tokenize(predicted.get("claim_b"))
    if expected_claim_tokens and predicted_claim_tokens:
        score += min(0.3, len(expected_claim_tokens & predicted_claim_tokens) / len(expected_claim_tokens))

    return min(score, 1.0)


def match_contradictions(
    expected: list[JsonObject],
    predicted: list[JsonObject],
    threshold: float = 0.55,
) -> list[tuple[int, int]]:
    matches: list[tuple[int, int]] = []
    used_predictions: set[int] = set()

    for expected_index, expected_item in enumerate(expected):
        best_prediction_index = None
        best_score = 0.0
        for predicted_index, predicted_item in enumerate(predicted):
            if predicted_index in used_predictions:
                continue
            score = contradiction_match_score(expected_item, predicted_item)
            if score > best_score:
                best_score = score
                best_prediction_index = predicted_index
        if best_prediction_index is not None and best_score >= threshold:
            used_predictions.add(best_prediction_index)
            matches.append((expected_index, best_prediction_index))

    return matches


def evidence_quality_for_match(expected: JsonObject, predicted: JsonObject) -> float:
    expected_chunks = set(expected.get("evidence_chunk_ids", set()))
    predicted_chunks = set(predicted.get("evidence_chunk_ids", set()))
    if not expected_chunks:
        return 1.0 if len(predicted_chunks) >= 2 else 0.0
    return len(expected_chunks & predicted_chunks) / len(expected_chunks)


def precision(true_positives: int, false_positives: int) -> float:
    denominator = true_positives + false_positives
    if denominator == 0:
        return 0.0
    return true_positives / denominator


def recall(true_positives: int, false_negatives: int) -> float:
    denominator = true_positives + false_negatives
    if denominator == 0:
        return 0.0
    return true_positives / denominator


def f1_score(precision_score: float, recall_score: float) -> float:
    denominator = precision_score + recall_score
    if denominator == 0:
        return 0.0
    return 2 * precision_score * recall_score / denominator


def score_contradiction_example(example: JsonObject, prediction: JsonObject | None) -> JsonObject:
    expected = expected_contradictions(example)
    predicted = predicted_contradictions(prediction or {})
    matches = match_contradictions(expected, predicted)
    matched_expected = {expected_index for expected_index, _ in matches}
    matched_predicted = {predicted_index for _, predicted_index in matches}

    true_positives = len(matches)
    false_positives = len(predicted) - true_positives
    false_negatives = len(expected) - true_positives
    evidence_scores = [
        evidence_quality_for_match(expected[expected_index], predicted[predicted_index])
        for expected_index, predicted_index in matches
    ]
    precision_score = precision(true_positives, false_positives)
    recall_score = recall(true_positives, false_negatives)

    return {
        "patient_id": example.get("patient_id"),
        "question": example.get("question"),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision_score, 4),
        "recall": round(recall_score, 4),
        "f1": round(f1_score(precision_score, recall_score), 4),
        "contradiction_evidence_quality": round(average(evidence_scores), 4),
        "missing_contradictions": [
            expected[index].get("subject") or expected[index].get("claim_a")
            for index in range(len(expected))
            if index not in matched_expected
        ],
        "extra_contradictions": [
            predicted[index].get("subject") or predicted[index].get("claim_a")
            for index in range(len(predicted))
            if index not in matched_predicted
        ],
    }


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def evaluate_contradictions(
    examples: list[JsonObject],
    predictions: dict[PredictionKey, JsonObject],
) -> JsonObject:
    per_example = [
        score_contradiction_example(example, predictions.get(prediction_key(example)))
        for example in examples
    ]
    true_positives = sum(row["true_positives"] for row in per_example)
    false_positives = sum(row["false_positives"] for row in per_example)
    false_negatives = sum(row["false_negatives"] for row in per_example)
    precision_score = precision(true_positives, false_positives)
    recall_score = recall(true_positives, false_negatives)

    return {
        "example_count": len(per_example),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision_score, 4),
        "recall": round(recall_score, 4),
        "f1": round(f1_score(precision_score, recall_score), 4),
        "contradiction_evidence_quality": round(
            average([row["contradiction_evidence_quality"] for row in per_example]),
            4,
        ),
        "per_example": per_example,
    }


def write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate clinical contradiction detection predictions."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/datasets/contradiction_cases.jsonl"),
        help="JSONL dataset with expected contradictions or CONTRAINDICATES cases.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="JSONL predictions with contradictions keyed by patient_id and question.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for writing JSON metrics.",
    )
    args = parser.parse_args()

    metrics = evaluate_contradictions(
        examples=load_jsonl(args.dataset),
        predictions=load_contradiction_predictions(args.predictions),
    )

    if args.output:
        write_json(args.output, metrics)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
