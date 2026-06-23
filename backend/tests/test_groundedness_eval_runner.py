import json
from pathlib import Path

from evals.run_groundedness_eval import (
    evaluate_groundedness,
    extract_evidence_texts,
    load_answer_predictions,
    score_answer_groundedness,
    split_claims,
)


def test_score_answer_groundedness_counts_supported_cited_and_unsupported_claims() -> None:
    prediction = {
        "answer": (
            "Dizziness was reported after metoprolol was increased [1]. "
            "The patient also had pneumonia."
        ),
        "retrieved_context": [
            {
                "chunk_id": "chunk_12",
                "text": "Metoprolol was increased. Dizziness was reported after the medication change.",
            }
        ],
    }

    score = score_answer_groundedness(prediction)

    assert score["groundedness"] == 0.5
    assert score["citation_coverage"] == 0.5
    assert score["unsupported_claims"] == 1
    assert score["supported_claims"][0]["has_citation"] is True
    assert score["unsupported_claim_details"][0]["claim"] == "The patient also had pneumonia."


def test_score_answer_groundedness_rewards_uncertainty_when_no_major_claims() -> None:
    prediction = {
        "answer": "Insufficient evidence is available to determine whether symptoms worsened.",
        "retrieved_context": [],
    }

    score = score_answer_groundedness(prediction)

    assert score["groundedness"] == 1.0
    assert score["citation_coverage"] == 1.0
    assert score["unsupported_claims"] == 0
    assert score["uncertainty_admitted"] is True


def test_evaluate_groundedness_returns_aggregate_metrics() -> None:
    examples = [
        {"patient_id": "patient-1", "question": "Question one?"},
        {"patient_id": "patient-2", "question": "Question two?"},
    ]
    predictions = {
        ("patient-1", "Question one?"): {
            "answer": "Metoprolol was increased before dizziness [1].",
            "retrieved_context": [
                {"text": "Metoprolol was increased before dizziness was documented."}
            ],
        },
        ("patient-2", "Question two?"): {
            "answer": "The record shows pneumonia.",
            "retrieved_context": [{"text": "The record discusses dizziness only."}],
        },
    }

    metrics = evaluate_groundedness(examples, predictions)

    assert metrics["example_count"] == 2
    assert metrics["groundedness"] == 0.5
    assert metrics["citation_coverage"] == 0.5
    assert metrics["unsupported_claims"] == 1


def test_extract_evidence_texts_accepts_common_prediction_shapes() -> None:
    prediction = {
        "retrieved_chunks": [{"content": "chunk content"}],
        "source_snippets": [{"snippet": "source snippet"}],
        "citations": [{"evidence_quote": "citation quote"}],
        "evidence": ["free text evidence"],
    }

    assert extract_evidence_texts(prediction) == [
        "chunk content",
        "source snippet",
        "free text evidence",
        "citation quote",
    ]


def test_split_claims_handles_newlines_and_sentence_endings() -> None:
    assert split_claims("First claim.\nSecond claim? Third claim!") == [
        "First claim.",
        "Second claim?",
        "Third claim!",
    ]


def test_load_answer_predictions_keys_rows_by_patient_and_question(tmp_path: Path) -> None:
    predictions_path = tmp_path / "answers.jsonl"
    predictions_path.write_text(
        json.dumps(
            {
                "patient_id": "patient-1",
                "question": "Question?",
                "answer": "Answer.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    predictions = load_answer_predictions(predictions_path)

    assert predictions[("patient-1", "Question?")]["answer"] == "Answer."
