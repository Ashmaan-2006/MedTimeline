const API_BASE_URL =
  process.env.API_URL_INTERNAL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Patient = {
  id: string;
  medical_record_number: string;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  sex: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type TimelineEvent = {
  id: string;
  patient_id: string;
  source_document_id: string | null;
  occurred_at: string | null;
  event_type: string;
  title: string;
  description: string | null;
  evidence_text: string | null;
  confidence: number | null;
  event_metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type PatientDocument = {
  id: string;
  patient_id: string;
  filename: string;
  content_type: string | null;
  storage_path: string;
  extracted_text: string | null;
  summary: string | null;
  processing_status: "uploaded" | "queued" | "processing" | "completed" | "failed";
  processing_error: string | null;
  processing_started_at: string | null;
  processing_completed_at: string | null;
  celery_task_id: string | null;
  processing_attempts: number;
  created_at: string;
  updated_at: string;
};

export type PatientGraphSummary = {
  patient_id: string;
  document_count: number;
  chunk_count: number;
  entity_count: number;
  relationship_count: number;
};

export type PatientGraphEntity = {
  label: string;
  normalized_name: string;
  name: string | null;
  mention_count: number;
  evidence_count: number;
  latest_seen_at: string | null;
};

export type PatientGraphRelationship = {
  source_label: string;
  source_name: string;
  relationship_type: string;
  target_label: string;
  target_name: string;
  evidence: string | null;
  confidence: number | null;
  source_chunk_id: string | null;
};

export type PatientGraphEvidenceChunk = {
  chunk_id: string;
  document_id: string;
  chunk_index: number | null;
  content: string;
  evidence: string | null;
  confidence: number | null;
  filename: string | null;
  created_at: string | null;
};

async function fetchJson<T>(path: string): Promise<T | null> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export function getPatient(patientId: string): Promise<Patient | null> {
  return fetchJson<Patient>(`/patients/${encodeURIComponent(patientId)}`);
}

export function getPatientTimelineEvents(patientId: string): Promise<TimelineEvent[] | null> {
  return fetchJson<TimelineEvent[]>(
    `/patients/${encodeURIComponent(patientId)}/timeline-events?limit=25`,
  );
}

export function getPatientDocuments(patientId: string): Promise<PatientDocument[] | null> {
  return fetchJson<PatientDocument[]>(`/patients/${encodeURIComponent(patientId)}/documents?limit=25`);
}

export function getPatientGraphSummary(patientId: string): Promise<PatientGraphSummary | null> {
  return fetchJson<PatientGraphSummary>(`/patients/${encodeURIComponent(patientId)}/graph/summary`);
}

export function getPatientGraphEntities(patientId: string): Promise<PatientGraphEntity[] | null> {
  return fetchJson<PatientGraphEntity[]>(`/patients/${encodeURIComponent(patientId)}/graph/entities`);
}

export function getPatientGraphRelationships(
  patientId: string,
): Promise<PatientGraphRelationship[] | null> {
  return fetchJson<PatientGraphRelationship[]>(
    `/patients/${encodeURIComponent(patientId)}/graph/relationships`,
  );
}

export function getPatientGraphEntityEvidence(
  patientId: string,
  entityName: string,
): Promise<PatientGraphEvidenceChunk[] | null> {
  return fetchJson<PatientGraphEvidenceChunk[]>(
    `/patients/${encodeURIComponent(patientId)}/graph/entity/${encodeURIComponent(entityName)}/evidence`,
  );
}
