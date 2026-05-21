const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

