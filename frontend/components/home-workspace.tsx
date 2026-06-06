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
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Create Patient</h2>
            <p className="panel-kicker">Start a longitudinal record</p>
          </div>
        </div>
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
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Document Processing</h2>
            <p className="panel-kicker">Upload notes, PDFs, and reports</p>
          </div>
        </div>
        <DocumentUploadForm patientId={activePatient?.id} showPatientIdField={false} />
      </div>
    </section>
  );
}
