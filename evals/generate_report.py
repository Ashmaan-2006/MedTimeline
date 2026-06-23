"""Generate a portfolio-ready MedGraph AI evaluation report."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import quantiles
from typing import Any


JsonObject = dict[str, Any]
DEFAULT_OUTPUT_DIR = Path("eval_reports")
DEFAULT_MARKDOWN_PATH = DEFAULT_OUTPUT_DIR / "latest.md"
DEFAULT_JSON_PATH = DEFAULT_OUTPUT_DIR / "latest.json"
DEFAULT_INPUTS = {
    "retrieval": Path("eval_reports/retrieval_metrics.json"),
    "graph": Path("eval_reports/graph_metrics.json"),
    "groundedness": Path("eval_reports/groundedness_metrics.json"),
    "timeline": Path("eval_reports/timeline_metrics.json"),
    "contradiction": Path("eval_reports/contradiction_metrics.json"),
}


def load_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path | None) -> list[JsonObject]:
    if path is None or not path.exists():
        return []
    rows = []
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


def percentile(values: list[float], percentile_value: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return round(sorted_values[0], 4)
    if percentile_value == 50:
        midpoint = len(sorted_values) // 2
        if len(sorted_values) % 2:
            return round(sorted_values[midpoint], 4)
        return round((sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2, 4)
    return round(quantiles(sorted_values, n=100, method="inclusive")[percentile_value - 1], 4)


def summarize_operations(rows: list[JsonObject]) -> JsonObject:
    latencies = [
        float(row["latency_ms"])
        for row in rows
        if isinstance(row.get("latency_ms"), int | float) and row.get("latency_ms") >= 0
    ]
    total_input_tokens = sum(int(row.get("tokens_input") or 0) for row in rows)
    total_output_tokens = sum(int(row.get("tokens_output") or 0) for row in rows)
    total_cost = sum(float(row.get("cost_usd") or 0.0) for row in rows)
    error_count = sum(int(row.get("error_count") or 0) for row in rows)
    explicit_failures = sum(1 for row in rows if str(row.get("status", "")).lower() == "failed")

    return {
        "operation_count": len(rows),
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "tokens_input": total_input_tokens,
        "tokens_output": total_output_tokens,
        "error_count": error_count + explicit_failures,
        "cost_estimate_usd": round(total_cost or estimate_token_cost(total_input_tokens, total_output_tokens), 6),
    }


def estimate_token_cost(tokens_input: int, tokens_output: int) -> float:
    input_cost_per_million = 0.15
    output_cost_per_million = 0.60
    return (
        (tokens_input / 1_000_000) * input_cost_per_million
        + (tokens_output / 1_000_000) * output_cost_per_million
    )


def known_failure_modes(metrics: JsonObject, operations: JsonObject) -> list[str]:
    failures = []
    retrieval = metrics.get("retrieval", {})
    graph = metrics.get("graph", {})
    groundedness = metrics.get("groundedness", {})
    timeline = metrics.get("timeline", {})
    contradiction = metrics.get("contradiction", {})

    if retrieval.get("recall_at_5", 1.0) < 0.8:
        failures.append("Vector retrieval missed expected evidence chunks in some cases.")
    if graph.get("relationship_recall", 1.0) < 0.8:
        failures.append("Graph retrieval missed expected clinical relationships.")
    if groundedness.get("unsupported_claims", 0) > 0:
        failures.append("Some generated answers contained unsupported claims.")
    if timeline.get("temporal_error_count", 0) > 0:
        failures.append("Timeline reasoning produced ordering or date errors.")
    if contradiction.get("false_negatives", 0) > 0:
        failures.append("Contradiction detection missed expected conflicts.")
    if operations.get("error_count", 0) > 0:
        failures.append("Operational traces reported failed calls or task errors.")
    if not failures:
        failures.append("No major failure modes were detected in the supplied eval artifacts.")
    return failures


def build_report_payload(
    retrieval: JsonObject,
    graph: JsonObject,
    groundedness: JsonObject,
    timeline: JsonObject,
    contradiction: JsonObject,
    operations_rows: list[JsonObject],
) -> JsonObject:
    operations = summarize_operations(operations_rows)
    metrics = {
        "retrieval": retrieval,
        "graph": graph,
        "groundedness": groundedness,
        "timeline": timeline,
        "contradiction": contradiction,
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "retrieval_recall_at_5": retrieval.get("recall_at_5", 0.0),
            "graph_relationship_recall": graph.get("relationship_recall", 0.0),
            "groundedness": groundedness.get("groundedness", 0.0),
            "timeline_event_order_accuracy": timeline.get("event_order_accuracy", 0.0),
            "contradiction_f1": contradiction.get("f1", 0.0),
            "latency_p50_ms": operations["latency_p50_ms"],
            "latency_p95_ms": operations["latency_p95_ms"],
            "cost_estimate_usd": operations["cost_estimate_usd"],
        },
        "metrics": metrics,
        "operations": operations,
        "known_failure_modes": known_failure_modes(metrics, operations),
    }


def metric_table(payload: JsonObject) -> str:
    rows = [
        ("Retrieval Recall@5", payload["summary"]["retrieval_recall_at_5"]),
        ("Graph Relationship Recall", payload["summary"]["graph_relationship_recall"]),
        ("Groundedness", payload["summary"]["groundedness"]),
        ("Timeline Event Order Accuracy", payload["summary"]["timeline_event_order_accuracy"]),
        ("Contradiction F1", payload["summary"]["contradiction_f1"]),
        ("Latency p50 ms", payload["summary"]["latency_p50_ms"]),
        ("Latency p95 ms", payload["summary"]["latency_p95_ms"]),
        ("Estimated Cost USD", payload["summary"]["cost_estimate_usd"]),
    ]
    lines = ["| Metric | Value |", "| --- | ---: |"]
    lines.extend(f"| {name} | {value} |" for name, value in rows)
    return "\n".join(lines)


def render_markdown(payload: JsonObject) -> str:
    failure_lines = "\n".join(
        f"- {failure}" for failure in payload["known_failure_modes"]
    )
    operations = payload["operations"]
    return f"""# MedGraph AI Evaluation Report

Generated: `{payload["generated_at"]}`

## Summary

{metric_table(payload)}

## Evaluation Coverage

- Retrieval metrics: Recall@3, Recall@5, Precision@5, MRR, missing chunks
- Graph metrics: entity recall, relationship recall, path relevance, evidence linkage
- Groundedness metrics: groundedness, citation coverage, unsupported claims
- Timeline metrics: event order accuracy, date accuracy, temporal error count
- Contradiction metrics: true positives, false positives, false negatives, F1, evidence quality

## Operational Metrics

- Operation count: `{operations["operation_count"]}`
- Input tokens: `{operations["tokens_input"]}`
- Output tokens: `{operations["tokens_output"]}`
- Error count: `{operations["error_count"]}`
- Cost estimate: `${operations["cost_estimate_usd"]}`

## Known Failure Modes

{failure_lines}

## Notes

This report is generated from local evaluation artifacts. Missing artifact files are treated as empty metrics so the report can still be generated during incremental development.
"""


def write_outputs(payload: JsonObject, markdown_path: Path, json_path: Path) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MedGraph AI evaluation report.")
    parser.add_argument("--retrieval", type=Path, default=DEFAULT_INPUTS["retrieval"])
    parser.add_argument("--graph", type=Path, default=DEFAULT_INPUTS["graph"])
    parser.add_argument("--groundedness", type=Path, default=DEFAULT_INPUTS["groundedness"])
    parser.add_argument("--timeline", type=Path, default=DEFAULT_INPUTS["timeline"])
    parser.add_argument("--contradiction", type=Path, default=DEFAULT_INPUTS["contradiction"])
    parser.add_argument("--operations", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_PATH)
    args = parser.parse_args()

    payload = build_report_payload(
        retrieval=load_json(args.retrieval),
        graph=load_json(args.graph),
        groundedness=load_json(args.groundedness),
        timeline=load_json(args.timeline),
        contradiction=load_json(args.contradiction),
        operations_rows=load_jsonl(args.operations),
    )
    write_outputs(payload, args.markdown_output, args.json_output)
    print(f"Wrote {args.markdown_output} and {args.json_output}")


if __name__ == "__main__":
    main()
