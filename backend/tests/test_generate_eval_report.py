import json
from pathlib import Path

from evals.generate_report import (
    build_report_payload,
    known_failure_modes,
    render_markdown,
    summarize_operations,
    write_outputs,
)


def test_summarize_operations_computes_latency_tokens_errors_and_cost() -> None:
    operations = summarize_operations(
        [
            {
                "latency_ms": 100,
                "tokens_input": 1000,
                "tokens_output": 100,
                "cost_usd": 0.01,
            },
            {
                "latency_ms": 300,
                "tokens_input": 2000,
                "tokens_output": 200,
                "error_count": 1,
            },
            {"latency_ms": 500, "status": "failed"},
        ]
    )

    assert operations["operation_count"] == 3
    assert operations["latency_p50_ms"] == 300
    assert operations["latency_p95_ms"] == 480
    assert operations["tokens_input"] == 3000
    assert operations["tokens_output"] == 300
    assert operations["error_count"] == 2
    assert operations["cost_estimate_usd"] == 0.01


def test_known_failure_modes_identifies_eval_regressions() -> None:
    failures = known_failure_modes(
        {
            "retrieval": {"recall_at_5": 0.5},
            "graph": {"relationship_recall": 0.4},
            "groundedness": {"unsupported_claims": 2},
            "timeline": {"temporal_error_count": 1},
            "contradiction": {"false_negatives": 1},
        },
        {"error_count": 1},
    )

    assert failures == [
        "Vector retrieval missed expected evidence chunks in some cases.",
        "Graph retrieval missed expected clinical relationships.",
        "Some generated answers contained unsupported claims.",
        "Timeline reasoning produced ordering or date errors.",
        "Contradiction detection missed expected conflicts.",
        "Operational traces reported failed calls or task errors.",
    ]


def test_build_report_payload_and_markdown_include_required_sections() -> None:
    payload = build_report_payload(
        retrieval={"recall_at_5": 0.82},
        graph={"relationship_recall": 0.74},
        groundedness={"groundedness": 0.9, "unsupported_claims": 0},
        timeline={"event_order_accuracy": 0.88, "temporal_error_count": 0},
        contradiction={"f1": 0.67, "false_negatives": 0},
        operations_rows=[{"latency_ms": 120, "tokens_input": 100, "tokens_output": 50}],
    )
    markdown = render_markdown(payload)

    assert payload["summary"]["retrieval_recall_at_5"] == 0.82
    assert payload["summary"]["graph_relationship_recall"] == 0.74
    assert payload["summary"]["groundedness"] == 0.9
    assert payload["summary"]["timeline_event_order_accuracy"] == 0.88
    assert payload["summary"]["contradiction_f1"] == 0.67
    assert "# MedGraph AI Evaluation Report" in markdown
    assert "## Known Failure Modes" in markdown
    assert "| Retrieval Recall@5 | 0.82 |" in markdown


def test_write_outputs_creates_markdown_and_json(tmp_path: Path) -> None:
    payload = build_report_payload(
        retrieval={},
        graph={},
        groundedness={},
        timeline={},
        contradiction={},
        operations_rows=[],
    )
    markdown_path = tmp_path / "latest.md"
    json_path = tmp_path / "latest.json"

    write_outputs(payload, markdown_path, json_path)

    assert markdown_path.exists()
    assert json_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"][
        "cost_estimate_usd"
    ] == 0.0
