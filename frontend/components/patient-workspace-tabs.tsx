"use client";

import { useState } from "react";

import { ClinicalGraphPanel } from "@/components/clinical-graph-panel";
import { DocumentUploadForm } from "@/components/document-upload-form";
import { RagChatPanel } from "@/components/rag-chat-panel";
import type {
  PatientDocument,
  PatientGraphEntity,
  PatientGraphEvidenceChunk,
  PatientGraphRelationship,
  PatientGraphSummary,
  TimelineEvent,
} from "@/lib/api";

type PatientWorkspaceTabsProps = {
  completedDocuments: PatientDocument[];
  documents: PatientDocument[];
  graphEntities: PatientGraphEntity[];
  graphEvidenceChunks: PatientGraphEvidenceChunk[];
  graphRelationships: PatientGraphRelationship[];
  graphSummary: PatientGraphSummary | null;
  patientId: string;
  timelineEvents: TimelineEvent[];
};

type WorkspaceTab = "timeline" | "documents" | "ask-ai" | "clinical-graph";

const TABS: { id: WorkspaceTab; label: string }[] = [
  { id: "timeline", label: "Timeline" },
  { id: "documents", label: "Documents" },
  { id: "ask-ai", label: "Ask AI" },
  { id: "clinical-graph", label: "Clinical Graph" },
];

function formatDateTime(value: string | null) {
  if (value === null) {
    return "Undated";
  }

  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatEventType(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function documentStatusLabel(document: PatientDocument) {
  switch (document.processing_status) {
    case "queued":
      return "Queued";
    case "processing":
      return "Processing";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return "Uploaded";
  }
}

function documentStatusClassName(document: PatientDocument) {
  return `document-status document-status-${document.processing_status}`;
}

function documentStatusMessage(document: PatientDocument) {
  switch (document.processing_status) {
    case "queued":
      return "Queued for processing.";
    case "processing":
      return "Processing document...";
    case "completed":
      return document.summary ?? "Completed. No summary was generated for this document.";
    case "failed":
      return document.processing_error ?? "Processing failed.";
    default:
      return "Uploaded and waiting to be queued.";
  }
}

export function PatientWorkspaceTabs({
  completedDocuments,
  documents,
  graphEntities,
  graphEvidenceChunks,
  graphRelationships,
  graphSummary,
  patientId,
  timelineEvents,
}: PatientWorkspaceTabsProps) {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("timeline");

  return (
    <section className="patient-workspace">
      <div className="workspace-tabs" role="tablist" aria-label="Patient workspace sections">
        {TABS.map((tab) => (
          <button
            aria-controls={`workspace-panel-${tab.id}`}
            aria-selected={activeTab === tab.id}
            className={`workspace-tab ${activeTab === tab.id ? "workspace-tab-active" : ""}`}
            id={`workspace-tab-${tab.id}`}
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            role="tab"
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div
        aria-labelledby="workspace-tab-timeline"
        hidden={activeTab !== "timeline"}
        id="workspace-panel-timeline"
        role="tabpanel"
      >
        <section className="panel timeline-panel">
          <h2 className="panel-title">Timeline Events</h2>
          {timelineEvents.length > 0 ? (
            <ol className="timeline-list">
              {timelineEvents.map((event) => (
                <li className="timeline-item" key={event.id}>
                  <div className="timeline-marker" aria-hidden="true" />
                  <div>
                    <div className="timeline-item-header">
                      <span className="event-type">{formatEventType(event.event_type)}</span>
                      <time>{formatDateTime(event.occurred_at)}</time>
                    </div>
                    <h3>{event.title}</h3>
                    {event.description !== null ? <p>{event.description}</p> : null}
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <div className="empty-state">No timeline events have been extracted for this patient.</div>
          )}
        </section>
      </div>

      <div
        aria-labelledby="workspace-tab-documents"
        hidden={activeTab !== "documents"}
        id="workspace-panel-documents"
        role="tabpanel"
      >
        <section className="panel upload-panel">
          <h2 className="panel-title">Upload Document</h2>
          <DocumentUploadForm patientId={patientId} />
        </section>

        <section className="panel document-panel">
          <h2 className="panel-title">Extracted Summaries</h2>
          {documents.length > 0 ? (
            <div className="document-summary-list">
              {documents.map((document) => (
                <article className="document-summary" key={document.id}>
                  <div className="document-summary-header">
                    <div>
                      <h3>{document.filename}</h3>
                      <time>{formatDateTime(document.created_at)}</time>
                    </div>
                    <span className={documentStatusClassName(document)}>
                      {documentStatusLabel(document)}
                    </span>
                  </div>
                  <p
                    className={
                      document.processing_status === "failed"
                        ? "document-summary-message document-summary-message-error"
                        : "document-summary-message"
                    }
                  >
                    {documentStatusMessage(document)}
                  </p>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state">Uploaded document summaries will appear here.</div>
          )}
        </section>
      </div>

      <div
        aria-labelledby="workspace-tab-ask-ai"
        hidden={activeTab !== "ask-ai"}
        id="workspace-panel-ask-ai"
        role="tabpanel"
      >
        <RagChatPanel documents={completedDocuments} patientId={patientId} />
      </div>

      <div
        aria-labelledby="workspace-tab-clinical-graph"
        hidden={activeTab !== "clinical-graph"}
        id="workspace-panel-clinical-graph"
        role="tabpanel"
      >
        <ClinicalGraphPanel
          entities={graphEntities}
          evidenceChunks={graphEvidenceChunks}
          relationships={graphRelationships}
          summary={graphSummary}
          timelineEvents={timelineEvents}
        />
      </div>
    </section>
  );
}
