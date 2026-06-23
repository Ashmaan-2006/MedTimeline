"""Evaluate clinical graph retrieval outputs against expected graph facts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]
PredictionKey = tuple[str, str]


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


def load_graph_predictions(path: Path) -> dict[PredictionKey, JsonObject]:
    return {prediction_key(row): row for row in load_jsonl(path)}


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def normalize_relationship(value: Any) -> str:
    text = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    return re.sub(r"_+", "_", text)


def extract_entity_names(prediction: JsonObject) -> set[str]:
    entities: set[str] = set()
    for item in prediction.get("retrieved_entities", []):
        if isinstance(item, dict):
            value = item.get("normalized_name") or item.get("name") or item.get("entity")
        else:
            value = item
        normalized = normalize_name(value)
        if normalized:
            entities.add(normalized)
    return entities


def extract_relationship_types(prediction: JsonObject) -> set[str]:
    relationships: set[str] = set()
    for item in prediction.get("retrieved_relationships", []):
        if isinstance(item, dict):
            value = item.get("type") or item.get("relationship_type") or item.get("label")
        else:
            value = item
        normalized = normalize_relationship(value)
        if normalized:
            relationships.add(normalized)
    return relationships


def extract_evidence_chunk_ids(prediction: JsonObject) -> set[str]:
    chunk_ids: set[str] = set()

    def add_chunk(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, list):
            for nested in value:
                add_chunk(nested)
            return
        if isinstance(value, dict):
            for key in ("chunk_id", "source_chunk_id", "evidence_chunk_id"):
                if key in value:
                    add_chunk(value[key])
            if "chunk_ids" in value:
                add_chunk(value["chunk_ids"])
            return
        normalized = str(value).strip()
        if normalized:
            chunk_ids.add(normalized)

    add_chunk(prediction.get("evidence_chunk_links", []))
    for relationship in prediction.get("retrieved_relationships", []):
        if isinstance(relationship, dict):
            add_chunk(relationship.get("evidence_chunk_ids"))
            add_chunk(relationship.get("source_chunk_id"))
            add_chunk(relationship.get("chunk_id"))
    for entity in prediction.get("retrieved_entities", []):
        if isinstance(entity, dict):
            add_chunk(entity.get("evidence_chunk_ids"))
            add_chunk(entity.get("source_chunk_id"))
            add_chunk(entity.get("chunk_id"))

    return chunk_ids


def extract_path_entities(path: Any) -> set[str]:
    entities: set[str] = set()
    if isinstance(path, dict):
        for entity in path.get("entities", []):
            entities.add(normalize_name(entity))
        for step in path.get("steps", []):
            if isinstance(step, dict):
                entities.add(normalize_name(step.get("source") or step.get("source_name")))
                entities.add(normalize_name(step.get("target") or step.get("target_name")))
    elif isinstance(path, list):
        for step in path:
            entities.update(extract_path_entities(step))
    return {entity for entity in entities if entity}


def extract_path_relationships(path: Any) -> set[str]:
    relationships: set[str] = set()
    if isinstance(path, dict):
        for relationship in path.get("relationships", []):
            relationships.add(normalize_relationship(relationship))
        for step in path.get("steps", []):
            if isinstance(step, dict):
                relationships.add(
                    normalize_relationship(
                        step.get("type")
                        or step.get("relationship_type")
                        or step.get("label")
                    )
                )
    elif isinstance(path, list):
        for step in path:
            relationships.update(extract_path_relationships(step))
    return {relationship for relationship in relationships if relationship}


def path_is_relevant(
    expected_entities: set[str],
    expected_relationships: set[str],
    prediction: JsonObject,
) -> bool:
    if not expected_entities and not expected_relationships:
        return False

    for path in prediction.get("retrieved_paths", []):
        path_entities = extract_path_entities(path)
        path_relationships = extract_path_relationships(path)
        connects_expected_entities = len(path_entities & expected_entities) >= 2
        contains_expected_relationship = bool(path_relationships & expected_relationships)
        if connects_expected_entities or contains_expected_relationship:
            return True

    return False


def recall(found: set[str], expected: set[str]) -> float:
    if not expected:
        return 1.0
    return len(found & expected) / len(expected)


def score_example(example: JsonObject, prediction: JsonObject | None) -> JsonObject:
    prediction = prediction or {}
    expected_entities = {normalize_name(item) for item in example.get("expected_entities", [])}
    expected_entities.discard("")
    expected_relationships = {
        normalize_relationship(item) for item in example.get("expected_relationships", [])
    }
    expected_relationships.discard("")
    expected_chunk_ids = {str(item).strip() for item in example.get("expected_chunk_ids", [])}
    expected_chunk_ids.discard("")

    found_entities = extract_entity_names(prediction)
    found_relationships = extract_relationship_types(prediction)
    found_chunk_ids = extract_evidence_chunk_ids(prediction)

    missing_entities = sorted(expected_entities - found_entities)
    missing_relationships = sorted(expected_relationships - found_relationships)
    missing_chunk_ids = sorted(expected_chunk_ids - found_chunk_ids)

    return {
        "patient_id": example.get("patient_id"),
        "question": example.get("question"),
        "entity_recall": recall(found_entities, expected_entities),
        "relationship_recall": recall(found_relationships, expected_relationships),
        "path_relevance": 1.0
        if path_is_relevant(expected_entities, expected_relationships, prediction)
        else 0.0,
        "evidence_chunk_linkage": recall(found_chunk_ids, expected_chunk_ids),
        "missing_entities": missing_entities,
        "missing_relationships": missing_relationships,
        "missing_evidence_chunk_ids": missing_chunk_ids,
    }


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def evaluate_graph_retrieval(
    examples: list[JsonObject],
    predictions: dict[PredictionKey, JsonObject],
) -> JsonObject:
    per_example = [
        score_example(example, predictions.get(prediction_key(example)))
        for example in examples
    ]
    return {
        "example_count": len(per_example),
        "entity_recall": average([row["entity_recall"] for row in per_example]),
        "relationship_recall": average(
            [row["relationship_recall"] for row in per_example]
        ),
        "path_relevance": average([row["path_relevance"] for row in per_example]),
        "evidence_chunk_linkage": average(
            [row["evidence_chunk_linkage"] for row in per_example]
        ),
        "per_example": per_example,
    }


def write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Neo4j graph retrieval outputs.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/datasets/rag_questions.jsonl"),
        help="JSONL eval dataset with expected entities, relationships, and chunks.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="JSONL graph retrieval predictions keyed by patient_id and question.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for writing JSON metrics.",
    )
    args = parser.parse_args()

    metrics = evaluate_graph_retrieval(
        examples=load_jsonl(args.dataset),
        predictions=load_graph_predictions(args.predictions),
    )

    if args.output:
        write_json(args.output, metrics)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
