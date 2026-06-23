"""Evaluate whether generated answers stay grounded in retrieved evidence."""

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
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}
UNCERTAINTY_PHRASES = (
    "cannot determine",
    "could not determine",
    "insufficient evidence",
    "limited evidence",
    "no evidence",
    "not enough evidence",
    "not available",
    "unclear",
    "unknown",
)
CITATION_PATTERN = re.compile(r"(?:\[\d+\]|\bchunk[_-][A-Za-z0-9_-]+\b)")
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


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


def load_answer_predictions(path: Path) -> dict[PredictionKey, JsonObject]:
    return {prediction_key(row): row for row in load_jsonl(path)}


def tokenize(text: str) -> set[str]:
    tokens = {
        token
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", text.lower())
        if len(token) > 2 and token not in STOPWORDS
    }
    return tokens


def split_claims(answer: str) -> list[str]:
    claims = []
    for sentence in SENTENCE_PATTERN.split(answer.replace("\n", " ")):
        sentence = sentence.strip()
        if sentence:
            claims.append(sentence)
    return claims


def admits_uncertainty(text: str) -> bool:
    normalized = text.lower()
    return any(phrase in normalized for phrase in UNCERTAINTY_PHRASES)


def extract_evidence_texts(prediction: JsonObject) -> list[str]:
    evidence_texts: list[str] = []

    def add_text(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                evidence_texts.append(stripped)
            return
        if isinstance(value, list):
            for item in value:
                add_text(item)
            return
        if isinstance(value, dict):
            for key in (
                "text",
                "content",
                "snippet",
                "evidence",
                "evidence_quote",
                "source_snippet",
            ):
                add_text(value.get(key))

    for key in (
        "retrieved_context",
        "retrieved_chunks",
        "source_snippets",
        "evidence",
        "citations",
    ):
        add_text(prediction.get(key))

    return evidence_texts


def claim_support_score(claim: str, evidence_texts: list[str]) -> float:
    claim_tokens = tokenize(strip_citations(claim))
    if not claim_tokens:
        return 0.0

    best_score = 0.0
    normalized_claim = normalize_text(strip_citations(claim))
    for evidence in evidence_texts:
        normalized_evidence = normalize_text(evidence)
        if normalized_claim and normalized_claim in normalized_evidence:
            return 1.0

        evidence_tokens = tokenize(evidence)
        if not evidence_tokens:
            continue
        best_score = max(best_score, len(claim_tokens & evidence_tokens) / len(claim_tokens))
    return best_score


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def strip_citations(text: str) -> str:
    return CITATION_PATTERN.sub("", text)


def has_attached_citation(claim: str) -> bool:
    return bool(CITATION_PATTERN.search(claim))


def score_answer_groundedness(
    prediction: JsonObject,
    support_threshold: float = 0.45,
) -> JsonObject:
    answer = str(prediction.get("answer") or prediction.get("final_answer") or "").strip()
    evidence_texts = extract_evidence_texts(prediction)
    claims = [
        claim
        for claim in split_claims(answer)
        if tokenize(strip_citations(claim)) and not admits_uncertainty(claim)
    ]

    supported_claims: list[JsonObject] = []
    unsupported_claims: list[JsonObject] = []
    cited_claim_count = 0

    for claim in claims:
        support_score = claim_support_score(claim, evidence_texts)
        cited = has_attached_citation(claim)
        if cited:
            cited_claim_count += 1

        result = {
            "claim": claim,
            "support_score": round(support_score, 4),
            "has_citation": cited,
        }
        if support_score >= support_threshold:
            supported_claims.append(result)
        else:
            unsupported_claims.append(result)

    if claims:
        groundedness = len(supported_claims) / len(claims)
        citation_coverage = cited_claim_count / len(claims)
    else:
        uncertainty = admits_uncertainty(answer)
        groundedness = 1.0 if uncertainty else 0.0
        citation_coverage = 1.0 if uncertainty else 0.0

    return {
        "groundedness": round(groundedness, 4),
        "citation_coverage": round(citation_coverage, 4),
        "unsupported_claims": len(unsupported_claims),
        "uncertainty_admitted": admits_uncertainty(answer),
        "claim_count": len(claims),
        "supported_claims": supported_claims,
        "unsupported_claim_details": unsupported_claims,
    }


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def evaluate_groundedness(
    examples: list[JsonObject],
    predictions: dict[PredictionKey, JsonObject],
) -> JsonObject:
    per_example = []
    for example in examples:
        prediction = predictions.get(prediction_key(example), {})
        score = score_answer_groundedness(prediction)
        per_example.append(
            {
                "patient_id": example.get("patient_id"),
                "question": example.get("question"),
                **score,
            }
        )

    return {
        "example_count": len(per_example),
        "groundedness": average([row["groundedness"] for row in per_example]),
        "citation_coverage": average([row["citation_coverage"] for row in per_example]),
        "unsupported_claims": sum(row["unsupported_claims"] for row in per_example),
        "uncertainty_admission_rate": average(
            [1.0 if row["uncertainty_admitted"] else 0.0 for row in per_example]
        ),
        "per_example": per_example,
    }


def write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate generated clinical answers for evidence groundedness."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/datasets/rag_questions.jsonl"),
        help="JSONL eval dataset keyed by patient_id and question.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="JSONL answers with answer text, citations, and retrieved evidence.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for writing JSON metrics.",
    )
    args = parser.parse_args()

    metrics = evaluate_groundedness(
        examples=load_jsonl(args.dataset),
        predictions=load_answer_predictions(args.predictions),
    )

    if args.output:
        write_json(args.output, metrics)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
