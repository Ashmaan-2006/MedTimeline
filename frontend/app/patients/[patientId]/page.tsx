import { notFound } from "next/navigation";

import { PatientWorkspaceTabs } from "@/components/patient-workspace-tabs";
import {
  getPatient,
  getPatientDocuments,
  getPatientGraphEntities,
  getPatientGraphEntityEvidence,
  getPatientGraphRelationships,
  getPatientGraphSummary,
  getPatientTimelineEvents,
} from "@/lib/api";

type PatientProfilePageProps = {
  params: Promise<{
    patientId: string;
  }>;
};

function formatDate(value: string | null) {
  if (value === null) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

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

export default async function PatientProfilePage({ params }: PatientProfilePageProps) {
  const { patientId } = await params;
  const [patient, documents, timelineEvents] = await Promise.all([
    getPatient(patientId),
    getPatientDocuments(patientId),
    getPatientTimelineEvents(patientId),
  ]);

  if (patient === null) {
    notFound();
  }

  const patientName = `${patient.first_name} ${patient.last_name}`;
  const patientDocuments = documents ?? [];
  const completedDocuments = patientDocuments.filter(
    (document) => document.processing_status === "completed",
  );
  const events = timelineEvents ?? [];
  const [graphSummary, graphEntities, graphRelationships] = await Promise.all([
    getPatientGraphSummary(patient.id).catch(() => null),
    getPatientGraphEntities(patient.id).catch(() => []),
    getPatientGraphRelationships(patient.id).catch(() => []),
  ]);
  const evidenceEntities = (graphEntities ?? []).slice(0, 6);
  const graphEvidenceChunks = (
    await Promise.all(
      evidenceEntities.map((entity) =>
        getPatientGraphEntityEvidence(patient.id, entity.normalized_name).catch(() => []),
      ),
    )
  )
    .flatMap((chunks) => chunks ?? [])
    .filter(
      (chunk, index, chunks) =>
        chunks.findIndex((candidate) => candidate.chunk_id === chunk.chunk_id) === index,
    );

  return (
    <>
      <section className="page-header">
        <div>
          <h1 className="page-title">{patientName}</h1>
          <p className="page-description">
            Longitudinal patient profile with demographics, clinical notes, and extracted timeline
            events.
          </p>
        </div>
        <div className="identifier-box">
          <span className="identifier-label">MRN</span>
          <span className="identifier-value">{patient.medical_record_number}</span>
        </div>
      </section>

      <section className="metric-row" aria-label="Patient metrics">
        <div className="metric">
          <div className="metric-label">Documents</div>
          <div className="metric-value">{patientDocuments.length}</div>
        </div>
        <div className="metric">
          <div className="metric-label">Date of Birth</div>
          <div className="metric-value metric-value-small">{formatDate(patient.date_of_birth)}</div>
        </div>
        <div className="metric">
          <div className="metric-label">Sex</div>
          <div className="metric-value metric-value-small">{patient.sex ?? "Unknown"}</div>
        </div>
      </section>

      <section className="profile-grid">
        <div className="panel">
          <h2 className="panel-title">Patient Details</h2>
          <dl className="detail-list">
            <div>
              <dt>Patient ID</dt>
              <dd>{patient.id}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDateTime(patient.created_at)}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{formatDateTime(patient.updated_at)}</dd>
            </div>
          </dl>
        </div>

        <div className="panel">
          <h2 className="panel-title">Clinical Notes</h2>
          <p className="notes-body">{patient.notes ?? "No patient notes have been recorded."}</p>
        </div>
      </section>

      <PatientWorkspaceTabs
        completedDocuments={completedDocuments}
        documents={patientDocuments}
        graphEntities={graphEntities ?? []}
        graphEvidenceChunks={graphEvidenceChunks}
        graphRelationships={graphRelationships ?? []}
        graphSummary={graphSummary}
        patientId={patient.id}
        timelineEvents={events}
      />
    </>
  );
}
