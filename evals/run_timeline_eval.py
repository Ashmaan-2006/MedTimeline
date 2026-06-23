"""Evaluate whether generated timeline answers preserve event order and dates."""

from __future__ import annotations

import argparse
import json
import re
from itertools import combinations
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]
PredictionKey = tuple[str, str]

STOPWORDS = {
    "a",
    "after",
    "an",
    "and",
    "at",
    "before",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "with",
}
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
ISO_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


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


def load_timeline_predictions(path: Path) -> dict[PredictionKey, JsonObject]:
    return {prediction_key(row): row for row in load_jsonl(path)}


def normalize_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def tokenize(text: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", normalize_text(text))
        if len(token) > 2 and token not in STOPWORDS
    }


def canonical_event(event: Any, index: int) -> JsonObject:
    if isinstance(event, str):
        return {
            "event_id": normalize_text(event).replace(" ", "_"),
            "text": event,
            "date": None,
            "expected_index": index,
        }

    text = (
        event.get("text")
        or event.get("description")
        or event.get("label")
        or event.get("summary")
        or event.get("event")
        or ""
    )
    return {
        "event_id": event.get("event_id") or event.get("id") or normalize_text(text).replace(" ", "_"),
        "text": text,
        "date": event.get("date") or event.get("occurred_at") or event.get("event_date"),
        "expected_index": index,
    }


def expected_events(example: JsonObject) -> list[JsonObject]:
    raw_events = (
        example.get("expected_timeline_events")
        or example.get("expected_events")
        or example.get("known_events")
        or example.get("expected_event_order")
        or []
    )
    return [canonical_event(event, index) for index, event in enumerate(raw_events)]


def prediction_events(prediction: JsonObject, expected: list[JsonObject]) -> list[JsonObject]:
    raw_events = (
        prediction.get("timeline_events")
        or prediction.get("timeline")
        or prediction.get("timeline_context")
        or prediction.get("answer_events")
        or []
    )
    if raw_events:
        return [canonical_prediction_event(event, index) for index, event in enumerate(raw_events)]

    return infer_events_from_answer(prediction, expected)


def canonical_prediction_event(event: Any, index: int) -> JsonObject:
    canonical = canonical_event(event, index)
    canonical["position"] = index
    return canonical


def infer_events_from_answer(prediction: JsonObject, expected: list[JsonObject]) -> list[JsonObject]:
    answer = str(prediction.get("answer") or prediction.get("final_answer") or "")
    sentences = [
        sentence.strip()
        for sentence in SENTENCE_PATTERN.split(answer.replace("\n", " "))
        if sentence.strip()
    ]
    inferred: list[JsonObject] = []
    for expected_event in expected:
        best_index = None
        best_score = 0.0
        expected_tokens = tokenize(expected_event["text"])
        for index, sentence in enumerate(sentences):
            sentence_tokens = tokenize(sentence)
            if not expected_tokens or not sentence_tokens:
                continue
            score = len(expected_tokens & sentence_tokens) / len(expected_tokens)
            if normalize_text(expected_event["text"]) in normalize_text(sentence):
                score = 1.0
            if score > best_score:
                best_score = score
                best_index = index

        if best_index is not None and best_score >= 0.4:
            inferred.append(
                {
                    "event_id": expected_event["event_id"],
                    "text": sentences[best_index],
                    "date": extract_date(sentences[best_index]),
                    "position": best_index,
                }
            )
    return inferred


def extract_date(text: str) -> str | None:
    match = ISO_DATE_PATTERN.search(text)
    if match:
        return match.group(0)
    return None


def event_similarity(expected_event: JsonObject, predicted_event: JsonObject) -> float:
    if expected_event.get("event_id") and expected_event.get("event_id") == predicted_event.get("event_id"):
        return 1.0

    expected_tokens = tokenize(expected_event.get("text"))
    predicted_tokens = tokenize(predicted_event.get("text"))
    if not expected_tokens:
        return 0.0
    return len(expected_tokens & predicted_tokens) / len(expected_tokens)


def match_events(
    expected: list[JsonObject],
    predicted: list[JsonObject],
    threshold: float = 0.4,
) -> dict[int, JsonObject]:
    matches: dict[int, JsonObject] = {}
    used_predictions: set[int] = set()

    for expected_index, expected_event in enumerate(expected):
        best_prediction_index = None
        best_score = 0.0
        for predicted_index, predicted_event in enumerate(predicted):
            if predicted_index in used_predictions:
                continue
            score = event_similarity(expected_event, predicted_event)
            if score > best_score:
                best_score = score
                best_prediction_index = predicted_index
        if best_prediction_index is not None and best_score >= threshold:
            used_predictions.add(best_prediction_index)
            matches[expected_index] = predicted[best_prediction_index]

    return matches


def event_order_accuracy(expected: list[JsonObject], matches: dict[int, JsonObject]) -> tuple[float, int]:
    pairs = list(combinations(range(len(expected)), 2))
    if not pairs:
        return (1.0 if len(expected) <= 1 else 0.0), 0

    correct_pairs = 0
    temporal_errors = 0
    for earlier_index, later_index in pairs:
        earlier = matches.get(earlier_index)
        later = matches.get(later_index)
        if earlier is None or later is None:
            temporal_errors += 1
            continue
        if int(earlier["position"]) < int(later["position"]):
            correct_pairs += 1
        else:
            temporal_errors += 1

    return correct_pairs / len(pairs), temporal_errors


def date_accuracy(expected: list[JsonObject], matches: dict[int, JsonObject]) -> tuple[float, int]:
    expected_with_dates = [
        (index, event) for index, event in enumerate(expected) if event.get("date")
    ]
    if not expected_with_dates:
        return 1.0, 0

    correct_dates = 0
    date_errors = 0
    for index, expected_event in expected_with_dates:
        predicted_event = matches.get(index)
        if predicted_event and str(predicted_event.get("date")) == str(expected_event.get("date")):
            correct_dates += 1
        else:
            date_errors += 1

    return correct_dates / len(expected_with_dates), date_errors


def score_timeline_example(example: JsonObject, prediction: JsonObject | None) -> JsonObject:
    prediction = prediction or {}
    expected = expected_events(example)
    predicted = prediction_events(prediction, expected)
    matches = match_events(expected, predicted)
    order_score, order_errors = event_order_accuracy(expected, matches)
    date_score, date_errors = date_accuracy(expected, matches)
    missing_event_count = len(expected) - len(matches)

    return {
        "patient_id": example.get("patient_id"),
        "question": example.get("question"),
        "event_order_accuracy": round(order_score, 4),
        "date_accuracy": round(date_score, 4),
        "temporal_error_count": order_errors + date_errors + missing_event_count,
        "matched_event_count": len(matches),
        "expected_event_count": len(expected),
        "missing_events": [
            expected[index]["text"]
            for index in range(len(expected))
            if index not in matches
        ],
    }


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def evaluate_timeline_consistency(
    examples: list[JsonObject],
    predictions: dict[PredictionKey, JsonObject],
) -> JsonObject:
    per_example = [
        score_timeline_example(example, predictions.get(prediction_key(example)))
        for example in examples
    ]
    return {
        "example_count": len(per_example),
        "event_order_accuracy": average(
            [row["event_order_accuracy"] for row in per_example]
        ),
        "date_accuracy": average([row["date_accuracy"] for row in per_example]),
        "temporal_error_count": sum(row["temporal_error_count"] for row in per_example),
        "per_example": per_example,
    }


def write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate generated timeline answers for temporal consistency."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/datasets/timeline_questions.jsonl"),
        help="JSONL dataset with expected_timeline_events or expected_event_order.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="JSONL predictions with timeline_events, timeline, or answer text.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for writing JSON metrics.",
    )
    args = parser.parse_args()

    metrics = evaluate_timeline_consistency(
        examples=load_jsonl(args.dataset),
        predictions=load_timeline_predictions(args.predictions),
    )

    if args.output:
        write_json(args.output, metrics)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
