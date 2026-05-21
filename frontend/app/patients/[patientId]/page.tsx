import { notFound } from "next/navigation";

import { DocumentUploadForm } from "@/components/document-upload-form";
import { getPatient, getPatientTimelineEvents } from "@/lib/api";

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

function formatEventType(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default async function PatientProfilePage({ params }: PatientProfilePageProps) {
  const { patientId } = await params;
  const [patient, timelineEvents] = await Promise.all([
    getPatient(patientId),
    getPatientTimelineEvents(patientId),
  ]);

  if (patient === null) {
    notFound();
  }

  const patientName = `${patient.first_name} ${patient.last_name}`;
  const events = timelineEvents ?? [];

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
          <div className="metric-label">Timeline Events</div>
          <div className="metric-value">{events.length}</div>
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

      <section className="panel upload-panel">
        <h2 className="panel-title">Upload Document</h2>
        <DocumentUploadForm patientId={patient.id} />
      </section>

      <section className="panel timeline-panel">
        <h2 className="panel-title">Timeline Events</h2>
        {events.length > 0 ? (
          <ol className="timeline-list">
            {events.map((event) => (
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
    </>
  );
}
