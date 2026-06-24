import { readFile } from "node:fs/promises";
import path from "node:path";

export const dynamic = "force-dynamic";

type EvalReport = {
  generated_at?: string;
  summary?: {
    retrieval_recall_at_5?: number;
    graph_relationship_recall?: number;
    groundedness?: number;
    timeline_event_order_accuracy?: number;
    contradiction_f1?: number;
    latency_p50_ms?: number;
    latency_p95_ms?: number;
    cost_estimate_usd?: number;
  };
  metrics?: {
    retrieval?: Record<string, unknown>;
    graph?: Record<string, unknown>;
    groundedness?: Record<string, unknown>;
    timeline?: Record<string, unknown>;
    contradiction?: Record<string, unknown>;
  };
  operations?: {
    operation_count?: number;
    error_count?: number;
    latency_p50_ms?: number;
    latency_p95_ms?: number;
    cost_estimate_usd?: number;
  };
  known_failure_modes?: string[];
};

type FailedRun = {
  label: string;
  detail: string;
};

async function readLatestReport(): Promise<EvalReport | null> {
  const reportPath = path.join(process.cwd(), "eval_reports", "latest.json");

  try {
    const raw = await readFile(reportPath, "utf-8");
    return JSON.parse(raw) as EvalReport;
  } catch {
    return null;
  }
}

function formatPercent(value: number | undefined): string {
  if (typeof value !== "number") {
    return "N/A";
  }
  return `${Math.round(value * 100)}%`;
}

function formatNumber(value: number | undefined, suffix = ""): string {
  if (typeof value !== "number") {
    return "N/A";
  }
  return `${value}${suffix}`;
}

function failureRate(report: EvalReport): number | undefined {
  const operationCount = report.operations?.operation_count;
  const errorCount = report.operations?.error_count;
  if (!operationCount || typeof errorCount !== "number") {
    return undefined;
  }
  return errorCount / operationCount;
}

function collectRecentFailedRuns(report: EvalReport): FailedRun[] {
  const failures: FailedRun[] = [];
  const metricGroups = report.metrics ?? {};

  for (const [groupName, group] of Object.entries(metricGroups)) {
    const perExample = group?.per_example;
    if (!Array.isArray(perExample)) {
      continue;
    }

    for (const item of perExample.slice(-8)) {
      if (!item || typeof item !== "object") {
        continue;
      }
      const row = item as Record<string, unknown>;
      const hasFailures =
        Number(row.unsupported_claims ?? 0) > 0 ||
        Number(row.temporal_error_count ?? 0) > 0 ||
        Number(row.false_negatives ?? 0) > 0 ||
        Number(row.false_positives ?? 0) > 0 ||
        Array.isArray(row.missing_expected_chunks) && row.missing_expected_chunks.length > 0 ||
        Array.isArray(row.missing_entities) && row.missing_entities.length > 0 ||
        Array.isArray(row.missing_relationships) && row.missing_relationships.length > 0;

      if (hasFailures) {
        failures.push({
          label: `${groupName}: ${String(row.patient_id ?? "unknown patient")}`,
          detail: String(row.question ?? "Evaluation case needs review"),
        });
      }
    }
  }

  return failures.slice(0, 6);
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="eval-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

export default async function EvaluationDashboardPage() {
  const report = await readLatestReport();

  if (report === null) {
    return (
      <>
        <section className="page-header">
          <div>
            <h1 className="page-title">Evaluation dashboard</h1>
            <p className="page-description">
              Track retrieval quality, groundedness, timeline reasoning, contradiction detection,
              latency, and failure modes from generated eval artifacts.
            </p>
          </div>
        </section>

        <section className="panel">
          <div className="empty-state eval-empty-state">
            <div>
              <strong>No evaluation report found.</strong>
              <p>
                Run <code>python evals\generate_report.py</code> from the repository root to
                generate <code>eval_reports/latest.json</code>.
              </p>
            </div>
          </div>
        </section>
      </>
    );
  }

  const summary = report.summary ?? {};
  const recentFailures = collectRecentFailedRuns(report);

  return (
    <>
      <section className="page-header">
        <div>
          <h1 className="page-title">Evaluation dashboard</h1>
          <p className="page-description">
            LLMOps view across retrieval, clinical graph reasoning, grounded answer quality,
            temporal consistency, and operational reliability.
          </p>
        </div>
        <div className="identifier-box">
          <span className="identifier-label">Report generated</span>
          <span className="identifier-value">
            {report.generated_at ? new Date(report.generated_at).toLocaleString() : "Unknown"}
          </span>
        </div>
      </section>

      <section className="eval-metric-grid" aria-label="Evaluation metrics">
        <MetricCard
          label="Average groundedness"
          value={formatPercent(summary.groundedness)}
          detail="Evidence-supported answer claims"
        />
        <MetricCard
          label="Retrieval recall@5"
          value={formatPercent(summary.retrieval_recall_at_5)}
          detail="Expected chunks retrieved"
        />
        <MetricCard
          label="Timeline accuracy"
          value={formatPercent(summary.timeline_event_order_accuracy)}
          detail="Correct event ordering"
        />
        <MetricCard
          label="Contradiction score"
          value={formatPercent(summary.contradiction_f1)}
          detail="Detection F1 across conflict cases"
        />
        <MetricCard
          label="Average latency"
          value={formatNumber(summary.latency_p50_ms, " ms")}
          detail={`p95 ${formatNumber(summary.latency_p95_ms, " ms")}`}
        />
        <MetricCard
          label="Failure rate"
          value={formatPercent(failureRate(report))}
          detail={`${formatNumber(report.operations?.error_count)} errors recorded`}
        />
      </section>

      <section className="eval-dashboard-grid">
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Recent Failed Runs</h2>
              <p className="panel-kicker">Cases with missing evidence, unsupported claims, or errors</p>
            </div>
          </div>
          {recentFailures.length > 0 ? (
            <ul className="eval-failure-list">
              {recentFailures.map((failure) => (
                <li key={`${failure.label}-${failure.detail}`}>
                  <strong>{failure.label}</strong>
                  <span>{failure.detail}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state eval-compact-empty">No failed runs in the latest report.</div>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Known Failure Modes</h2>
              <p className="panel-kicker">Generated from eval metric thresholds</p>
            </div>
          </div>
          <ul className="eval-failure-mode-list">
            {(report.known_failure_modes ?? []).map((failure) => (
              <li key={failure}>{failure}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="panel eval-detail-panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Operational Summary</h2>
            <p className="panel-kicker">Latency, cost, and trace-derived execution totals</p>
          </div>
        </div>
        <div className="eval-detail-grid">
          <div>
            <span>Operations</span>
            <strong>{formatNumber(report.operations?.operation_count)}</strong>
          </div>
          <div>
            <span>Latency p50</span>
            <strong>{formatNumber(report.operations?.latency_p50_ms, " ms")}</strong>
          </div>
          <div>
            <span>Latency p95</span>
            <strong>{formatNumber(report.operations?.latency_p95_ms, " ms")}</strong>
          </div>
          <div>
            <span>Cost estimate</span>
            <strong>${formatNumber(summary.cost_estimate_usd)}</strong>
          </div>
        </div>
      </section>
    </>
  );
}
