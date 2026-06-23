import json
from pathlib import Path

from evals.run_timeline_eval import (
    evaluate_timeline_consistency,
    infer_events_from_answer,
    load_timeline_predictions,
    score_timeline_example,
)


def test_score_timeline_example_scores_correct_order_and_dates() -> None:
    example = {
        "patient_id": "patient-1",
        "question": "What happened around dizziness?",
        "expected_timeline_events": [
            {
                "event_id": "dose_increase",
                "date": "2026-03-01",
                "text": "medication dose increased",
            },
            {
                "event_id": "dizziness",
                "date": "2026-03-03",
                "text": "dizziness reported",
            },
            {
                "event_id": "medication_stopped",
                "date": "2026-03-05",
                "text": "medication stopped",
            },
        ],
    }
    prediction = {
        "timeline_events": [
            {
                "event_id": "dose_increase",
                "date": "2026-03-01",
                "text": "medication dose increased",
            },
            {
                "event_id": "dizziness",
                "date": "2026-03-03",
                "text": "dizziness reported",
            },
            {
                "event_id": "medication_stopped",
                "date": "2026-03-05",
                "text": "medication stopped",
            },
        ]
    }

    score = score_timeline_example(example, prediction)

    assert score["event_order_accuracy"] == 1.0
    assert score["date_accuracy"] == 1.0
    assert score["temporal_error_count"] == 0
    assert score["matched_event_count"] == 3


def test_score_timeline_example_detects_reversed_events_and_bad_dates() -> None:
    example = {
        "patient_id": "patient-1",
        "question": "What happened around dizziness?",
        "expected_timeline_events": [
            {
                "event_id": "dose_increase",
                "date": "2026-03-01",
                "text": "medication dose increased",
            },
            {
                "event_id": "dizziness",
                "date": "2026-03-03",
                "text": "dizziness reported",
            },
        ],
    }
    prediction = {
        "timeline_events": [
            {
                "event_id": "dizziness",
                "date": "2026-03-03",
                "text": "dizziness reported",
            },
            {
                "event_id": "dose_increase",
                "date": "2026-03-02",
                "text": "medication dose increased",
            },
        ]
    }

    score = score_timeline_example(example, prediction)

    assert score["event_order_accuracy"] == 0.0
    assert score["date_accuracy"] == 0.5
    assert score["temporal_error_count"] == 2


def test_infer_events_from_answer_uses_sentence_order_when_structured_timeline_missing() -> None:
    expected = [
        {
            "event_id": "dose_increase",
            "date": "2026-03-01",
            "text": "medication dose increased",
        },
        {
            "event_id": "dizziness",
            "date": "2026-03-03",
            "text": "dizziness reported",
        },
    ]
    prediction = {
        "answer": (
            "On 2026-03-01, the medication dose increased. "
            "On 2026-03-03, dizziness was reported."
        )
    }

    inferred = infer_events_from_answer(prediction, expected)

    assert [event["event_id"] for event in inferred] == ["dose_increase", "dizziness"]
    assert [event["position"] for event in inferred] == [0, 1]
    assert [event["date"] for event in inferred] == ["2026-03-01", "2026-03-03"]


def test_evaluate_timeline_consistency_returns_aggregate_metrics() -> None:
    examples = [
        {
            "patient_id": "patient-1",
            "question": "Question one?",
            "expected_timeline_events": [
                {"event_id": "first", "date": "2026-01-01", "text": "first event"},
                {"event_id": "second", "date": "2026-01-02", "text": "second event"},
            ],
        },
        {
            "patient_id": "patient-2",
            "question": "Question two?",
            "expected_timeline_events": [
                {"event_id": "alpha", "date": "2026-02-01", "text": "alpha event"},
                {"event_id": "beta", "date": "2026-02-02", "text": "beta event"},
            ],
        },
    ]
    predictions = {
        ("patient-1", "Question one?"): {
            "timeline_events": [
                {"event_id": "first", "date": "2026-01-01", "text": "first event"},
                {"event_id": "second", "date": "2026-01-02", "text": "second event"},
            ]
        },
        ("patient-2", "Question two?"): {
            "timeline_events": [
                {"event_id": "beta", "date": "2026-02-02", "text": "beta event"},
                {"event_id": "alpha", "date": "2026-02-01", "text": "alpha event"},
            ]
        },
    }

    metrics = evaluate_timeline_consistency(examples, predictions)

    assert metrics["example_count"] == 2
    assert metrics["event_order_accuracy"] == 0.5
    assert metrics["date_accuracy"] == 1.0
    assert metrics["temporal_error_count"] == 1


def test_load_timeline_predictions_keys_rows_by_patient_and_question(tmp_path: Path) -> None:
    predictions_path = tmp_path / "timeline_predictions.jsonl"
    predictions_path.write_text(
        json.dumps(
            {
                "patient_id": "patient-1",
                "question": "Question?",
                "timeline_events": [{"event_id": "event-1", "text": "event"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    predictions = load_timeline_predictions(predictions_path)

    assert predictions[("patient-1", "Question?")]["timeline_events"] == [
        {"event_id": "event-1", "text": "event"}
    ]
