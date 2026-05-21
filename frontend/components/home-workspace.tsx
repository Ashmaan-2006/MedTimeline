"use client";

import Link from "next/link";
import { useState } from "react";

import { CreatePatientForm } from "@/components/create-patient-form";
import { DocumentUploadForm } from "@/components/document-upload-form";
import type { Patient } from "@/lib/api";

export function HomeWorkspace() {
  const [activePatient, setActivePatient] = useState<Patient | null>(null);

  return (
    <section className="workspace-grid">
      <div className="panel">
        <h2 className="panel-title">Create Patient</h2>
        <CreatePatientForm onPatientCreated={setActivePatient} />
        {activePatient !== null ? (
          <div className="created-patient">
            <span>Active patient</span>
            <strong>
              {activePatient.first_name} {activePatient.last_name}
            </strong>
            <code>{activePatient.id}</code>
            <Link className="inline-link" href={`/patients/${activePatient.id}`}>
              Open profile
            </Link>
          </div>
        ) : null}
      </div>
      <div className="panel">
        <h2 className="panel-title">Document Processing</h2>
        <DocumentUploadForm patientId={activePatient?.id} showPatientIdField={false} />
      </div>
    </section>
  );
}
