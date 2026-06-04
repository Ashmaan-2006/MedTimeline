"use client";

import { FormEvent, useMemo, useState } from "react";

import type { PatientDocument } from "@/lib/api";

type RagSource = {
  citation_label: string;
  chunk_id: string;
  document_id: string;
  patient_id: string;
  chunk_index: number;
  content: string;
  embedding_model: string | null;
  token_count: number | null;
  chunk_metadata: Record<string, unknown> | null;
  created_at: string;
};

type RagResponse = {
  patient_id: string;
  question: string;
  answer: string;
  sources: RagSource[];
};

type ChatMessage =
  | {
      id: string;
      role: "user";
      content: string;
    }
  | {
      id: string;
      role: "assistant";
      content: string;
      sources: RagSource[];
    };

type RagChatPanelProps = {
  patientId: string;
  documents: PatientDocument[];
};

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function documentLabel(document: PatientDocument) {
  return `${document.filename} (${formatDateTime(document.created_at)})`;
}

export function RagChatPanel({ patientId, documents }: RagChatPanelProps) {
  const [question, setQuestion] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<"idle" | "asking">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [failedQuestion, setFailedQuestion] = useState<string | null>(null);

  const documentsById = useMemo(
    () => new Map(documents.map((document) => [document.id, document])),
    [documents],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuestion = question.trim();
    if (trimmedQuestion.length === 0) {
      setErrorMessage("Enter a question before querying the patient record.");
      return;
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmedQuestion,
    };

    setMessages((currentMessages) => [...currentMessages, userMessage]);
    setQuestion("");
    setStatus("asking");
    setErrorMessage(null);
    setFailedQuestion(null);

    const payload = {
      question: trimmedQuestion,
      limit: 5,
      document_id: documentId || undefined,
      created_from: createdFrom ? `${createdFrom}T00:00:00.000Z` : undefined,
      created_to: createdTo ? `${createdTo}T23:59:59.999Z` : undefined,
    };

    let response: Response;
    try {
      response = await fetch(`/api/patients/${patientId}/rag/query`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify(payload),
      });
    } catch {
      setStatus("idle");
      setFailedQuestion(trimmedQuestion);
      setErrorMessage("Unable to reach the RAG service. Check that the backend is running and try again.");
      return;
    }

    if (!response.ok) {
      let detail = "RAG query failed. Check that the backend service is running.";
      try {
        const error = (await response.json()) as { detail?: unknown };
        detail = typeof error.detail === "string" ? error.detail : detail;
      } catch {
        // Keep the default message when the proxy returns a non-JSON error body.
      }

      setStatus("idle");
      setFailedQuestion(trimmedQuestion);
      setErrorMessage(detail);
      return;
    }

    const ragResponse = (await response.json()) as RagResponse;
    setMessages((currentMessages) => [
      ...currentMessages,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: ragResponse.answer,
        sources: ragResponse.sources,
      },
    ]);
    setStatus("idle");
  }

  function retryFailedQuestion() {
    if (failedQuestion === null) {
      return;
    }

    setQuestion(failedQuestion);
    setErrorMessage(null);
    setFailedQuestion(null);
  }

  return (
    <section className="panel rag-panel">
      <div className="rag-panel-header">
        <div>
          <h2 className="panel-title">Clinical RAG Chat</h2>
          <p className="rag-panel-subtitle">Ask patient-specific questions grounded in uploaded documents.</p>
        </div>
      </div>

      <div className="rag-chat-log" aria-busy={status === "asking"} aria-live="polite">
        {messages.length > 0 ? (
          messages.map((message) => (
            <article className={`chat-message chat-message-${message.role}`} key={message.id}>
              <div className="chat-role">{message.role === "user" ? "You" : "MedGraph"}</div>
              <p>{message.content}</p>
              {message.role === "assistant" && message.sources.length > 0 ? (
                <div className="citation-list">
                  {message.sources.map((source) => {
                    const sourceDocument = documentsById.get(source.document_id);
                    return (
                      <details className="citation-item" key={source.chunk_id}>
                        <summary>
                          <span>{source.citation_label}</span>
                          {sourceDocument?.filename ?? "Source document"}
                        </summary>
                        <p>{source.content}</p>
                        <div className="citation-meta">
                          Chunk {source.chunk_index + 1} · {formatDateTime(source.created_at)}
                        </div>
                      </details>
                    );
                  })}
                </div>
              ) : null}
            </article>
          ))
        ) : (
          <div className="empty-state rag-empty-state">
            Ask about medication changes, symptom progression, abnormal findings, or prior document evidence.
          </div>
        )}
        {status === "asking" ? (
          <article className="chat-message chat-message-assistant chat-message-loading">
            <div className="chat-role">MedGraph</div>
            <div className="loading-line">
              <span />
              <span />
              <span />
            </div>
            <p>Retrieving patient evidence and generating a cited answer.</p>
          </article>
        ) : null}
        {errorMessage !== null ? (
          <div className="rag-error-state" role="alert">
            <div>
              <strong>RAG chat needs attention</strong>
              <p>{errorMessage}</p>
            </div>
            {failedQuestion !== null ? (
              <button className="secondary-button" onClick={retryFailedQuestion} type="button">
                Restore question
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      <form className="rag-form" onSubmit={handleSubmit}>
        <div className="rag-filter-row">
          <label>
            Document
            <select
              className="select-input"
              disabled={status === "asking"}
              onChange={(event) => setDocumentId(event.target.value)}
              value={documentId}
            >
              <option value="">All documents</option>
              {documents.map((document) => (
                <option key={document.id} value={document.id}>
                  {documentLabel(document)}
                </option>
              ))}
            </select>
          </label>
          <label>
            From
            <input
              className="text-input"
              disabled={status === "asking"}
              onChange={(event) => setCreatedFrom(event.target.value)}
              type="date"
              value={createdFrom}
            />
          </label>
          <label>
            To
            <input
              className="text-input"
              disabled={status === "asking"}
              onChange={(event) => setCreatedTo(event.target.value)}
              type="date"
              value={createdTo}
            />
          </label>
        </div>

        <label className="rag-question-label" htmlFor="rag-question">
          Question
        </label>
        <div className="rag-question-row">
          <textarea
            className="textarea-input rag-question-input"
            disabled={status === "asking"}
            id="rag-question"
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Why did this patient's symptoms worsen?"
            rows={3}
            value={question}
          />
          <button className="primary-button rag-submit-button" disabled={status === "asking"} type="submit">
            {status === "asking" ? "Asking..." : "Ask"}
          </button>
        </div>
      </form>
    </section>
  );
}
