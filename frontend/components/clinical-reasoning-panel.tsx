"use client";

import { FormEvent, useMemo, useState } from "react";

type AgentCitation = {
  label?: string;
  source_type?: string;
  evidence_id?: string | null;
  related_evidence_id?: string | null;
  document_id?: string | null;
  snippet?: string | null;
};

type AgentResponse = {
  answer: string;
  intent: string | null;
  timeline: Record<string, unknown>[];
  contradictions: Record<string, unknown>[];
  risk_flags: Record<string, unknown>[];
  citations: AgentCitation[];
  confidence: string | null;
  limitations: string[];
};

type ClinicalReasoningPanelProps = {
  patientId: string;
};

function formatLabel(value: unknown) {
  if (typeof value !== "string" || value.length === 0) {
    return "Unknown";
  }

  return value
    .replaceAll("_", " ")
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function textValue(value: unknown, fallback = "Not available") {
  if (typeof value === "string" && value.trim().length > 0) {
    return value;
  }

  if (typeof value === "number") {
    return String(value);
  }

  return fallback;
}

function evidenceIds(value: unknown) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

export function ClinicalReasoningPanel({ patientId }: ClinicalReasoningPanelProps) {
  const [question, setQuestion] = useState("Did symptoms worsen after the medication change?");
  const [result, setResult] = useState<AgentResponse | null>(null);
  const [status, setStatus] = useState<"idle" | "asking">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const evidenceReviewed = useMemo(() => {
    if (result === null) {
      return [];
    }

    return result.citations.slice(0, 6);
  }, [result]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuestion = question.trim();
    if (trimmedQuestion.length === 0) {
      setErrorMessage("Enter a clinical question before running the reasoning workflow.");
      return;
    }

    setStatus("asking");
    setErrorMessage(null);

    let response: Response;
    try {
      response = await fetch(`/api/patients/${patientId}/agent/query`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({ question: trimmedQuestion }),
      });
    } catch {
      setStatus("idle");
      setErrorMessage("Unable to reach the clinical reasoning service. Check the backend and try again.");
      return;
    }

    if (!response.ok) {
      let detail = "Clinical reasoning query failed. Check that the backend service is running.";
      try {
        const error = (await response.json()) as { detail?: unknown };
        detail = typeof error.detail === "string" ? error.detail : detail;
      } catch {
        // Keep the default message for non-JSON proxy failures.
      }

      setStatus("idle");
      setErrorMessage(detail);
      return;
    }

    setResult((await response.json()) as AgentResponse);
    setStatus("idle");
  }

  return (
    <section className="panel reasoning-panel">
      <div className="rag-panel-header">
        <div>
          <h2 className="panel-title">Clinical Reasoning</h2>
          <p className="rag-panel-subtitle">
            Inspect structured evidence, timeline reasoning, conflicts, and follow-up flags.
          </p>
        </div>
        {result?.confidence ? (
          <span className="reasoning-confidence">{formatLabel(result.confidence)} confidence</span>
        ) : null}
      </div>

      <form className="reasoning-form" onSubmit={handleSubmit}>
        <label className="rag-question-label" htmlFor="reasoning-question">
          Question
        </label>
        <div className="rag-question-row">
          <textarea
            className="textarea-input rag-question-input"
            disabled={status === "asking"}
            id="reasoning-question"
            onChange={(event) => setQuestion(event.target.value)}
            rows={3}
            value={question}
          />
          <button className="primary-button rag-submit-button" disabled={status === "asking"} type="submit">
            {status === "asking" ? "Running..." : "Run"}
          </button>
        </div>
      </form>

      {errorMessage !== null ? (
        <div className="rag-error-state reasoning-error" role="alert">
          <div>
            <strong>Reasoning needs attention</strong>
            <p>{errorMessage}</p>
          </div>
        </div>
      ) : null}

      {status === "asking" ? (
        <article className="chat-message chat-message-assistant chat-message-loading reasoning-loading">
          <div className="chat-role">MedGraph</div>
          <div className="loading-line">
            <span />
            <span />
            <span />
          </div>
          <p>Running intent classification, retrieval, timeline ordering, conflict checks, and risk flagging.</p>
        </article>
      ) : null}

      {result === null ? (
        <div className="empty-state reasoning-empty-state">
          Run a question to inspect the structured reasoning outputs behind the answer.
        </div>
      ) : (
        <div className="reasoning-result">
          <section className="reasoning-answer">
            <div className="reasoning-section-header">
              <h3>Answer</h3>
              <span>{formatLabel(result.intent)}</span>
            </div>
            <p>{result.answer}</p>
            {result.limitations.length > 0 ? (
              <ul className="reasoning-limitation-list">
                {result.limitations.map((limitation) => (
                  <li key={limitation}>{limitation}</li>
                ))}
              </ul>
            ) : null}
          </section>

          <section className="reasoning-section">
            <div className="reasoning-section-header">
              <h3>Evidence Reviewed</h3>
              <span>{evidenceReviewed.length} items</span>
            </div>
            {evidenceReviewed.length > 0 ? (
              <div className="reasoning-card-grid">
                {evidenceReviewed.map((citation, index) => (
                  <article className="reasoning-card" key={`${citation.label}-${index}`}>
                    <strong>{citation.label ?? `Source ${index + 1}`}</strong>
                    <span>{formatLabel(citation.source_type)}</span>
                    <p>{citation.snippet ?? "Evidence snippet unavailable."}</p>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state reasoning-compact-empty">No evidence was retrieved.</div>
            )}
          </section>

          <section className="reasoning-section">
            <div className="reasoning-section-header">
              <h3>Timeline Used</h3>
              <span>{result.timeline.length} events</span>
            </div>
            {result.timeline.length > 0 ? (
              <ol className="reasoning-timeline-list">
                {result.timeline.map((event, index) => (
                  <li key={`${textValue(event.chunk_id ?? event.event_id, "event")}-${index}`}>
                    <span>{textValue(event.display_date, "Undated")}</span>
                    <p>{textValue(event.summary ?? event.narrative, "Timeline evidence was used.")}</p>
                  </li>
                ))}
              </ol>
            ) : (
              <div className="empty-state reasoning-compact-empty">No timeline evidence was used.</div>
            )}
          </section>

          <section className="reasoning-two-column">
            <div className="reasoning-section">
              <div className="reasoning-section-header">
                <h3>Possible Conflicts</h3>
                <span>{result.contradictions.length} found</span>
              </div>
              {result.contradictions.length > 0 ? (
                <div className="reasoning-stack">
                  {result.contradictions.map((conflict, index) => (
                    <article className="reasoning-card" key={`${textValue(conflict.subject)}-${index}`}>
                      <strong>{formatLabel(conflict.subject)}</strong>
                      <span>{formatLabel(conflict.severity)} severity</span>
                      <p>{textValue(conflict.claim_a)}</p>
                      <p>{textValue(conflict.claim_b)}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state reasoning-compact-empty">No conflicts were identified.</div>
              )}
            </div>

            <div className="reasoning-section">
              <div className="reasoning-section-header">
                <h3>Follow-up Flags</h3>
                <span>{result.risk_flags.length} flags</span>
              </div>
              {result.risk_flags.length > 0 ? (
                <div className="reasoning-stack">
                  {result.risk_flags.map((flag, index) => (
                    <article className="reasoning-card" key={`${textValue(flag.category)}-${index}`}>
                      <strong>{textValue(flag.title, formatLabel(flag.category))}</strong>
                      <span>{formatLabel(flag.severity)}</span>
                      <p>{textValue(flag.rationale)}</p>
                      {evidenceIds(flag.evidence_ids).length > 0 ? (
                        <small>Evidence: {evidenceIds(flag.evidence_ids).join(", ")}</small>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state reasoning-compact-empty">No follow-up flags were found.</div>
              )}
            </div>
          </section>

          <section className="reasoning-section">
            <div className="reasoning-section-header">
              <h3>Sources</h3>
              <span>{result.citations.length} citations</span>
            </div>
            {result.citations.length > 0 ? (
              <div className="citation-list reasoning-source-list">
                {result.citations.map((citation, index) => (
                  <details className="citation-item" key={`${citation.label}-${index}`}>
                    <summary>
                      <span>{citation.label ?? `[${index + 1}]`}</span>
                      {formatLabel(citation.source_type)}
                    </summary>
                    <p>{citation.snippet ?? "Citation snippet unavailable."}</p>
                    <div className="citation-meta">
                      {citation.evidence_id ? `Evidence ${citation.evidence_id}` : "Evidence ID unavailable"}
                    </div>
                  </details>
                ))}
              </div>
            ) : (
              <div className="empty-state reasoning-compact-empty">No sources were cited.</div>
            )}
          </section>
        </div>
      )}
    </section>
  );
}
