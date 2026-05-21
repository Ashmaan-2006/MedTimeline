"use client";

import { FormEvent, useState } from "react";

import type { Patient } from "@/lib/api";

type CreatePatientFormProps = {
  onPatientCreated: (patient: Patient) => void;
};

type ApiError = {
  detail?: string;
};

export function CreatePatientForm({ onPatientCreated }: CreatePatientFormProps) {
  const [status, setStatus] = useState<"idle" | "creating" | "success" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const medicalRecordNumber = String(formData.get("medical_record_number") ?? "").trim();
    const firstName = String(formData.get("first_name") ?? "").trim();
    const lastName = String(formData.get("last_name") ?? "").trim();
    const dateOfBirth = String(formData.get("date_of_birth") ?? "").trim();
    const sex = String(formData.get("sex") ?? "").trim();
    const notes = String(formData.get("notes") ?? "").trim();

    if (medicalRecordNumber.length === 0 || firstName.length === 0 || lastName.length === 0) {
      setStatus("error");
      setMessage("MRN, first name, and last name are required.");
      return;
    }

    setStatus("creating");
    setMessage(null);

    const response = await fetch("/api/patients", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        medical_record_number: medicalRecordNumber,
        first_name: firstName,
        last_name: lastName,
        date_of_birth: dateOfBirth.length > 0 ? dateOfBirth : null,
        sex: sex.length > 0 ? sex : null,
        notes: notes.length > 0 ? notes : null,
      }),
    });

    if (!response.ok) {
      setStatus("error");
      const error = (await response.json().catch(() => null)) as ApiError | null;
      setMessage(
        response.status === 409
          ? "A patient with that MRN already exists."
          : error?.detail ?? "Patient creation failed. Check that the backend service is running.",
      );
      return;
    }

    const patient = (await response.json()) as Patient;
    onPatientCreated(patient);
    setStatus("success");
    setMessage(`Created ${patient.first_name} ${patient.last_name}.`);
    event.currentTarget.reset();
  }

  return (
    <form className="patient-form" onSubmit={handleSubmit}>
      <div className="form-grid-two">
        <label>
          <span>MRN</span>
          <input className="text-input" name="medical_record_number" placeholder="MRN-001" type="text" />
        </label>
        <label>
          <span>Date of Birth</span>
          <input className="text-input" name="date_of_birth" type="date" />
        </label>
        <label>
          <span>First Name</span>
          <input className="text-input" name="first_name" placeholder="Maya" type="text" />
        </label>
        <label>
          <span>Last Name</span>
          <input className="text-input" name="last_name" placeholder="Singh" type="text" />
        </label>
      </div>
      <label>
        <span>Sex</span>
        <input className="text-input" name="sex" placeholder="female" type="text" />
      </label>
      <label>
        <span>Notes</span>
        <textarea className="textarea-input" name="notes" placeholder="Brief clinical context" rows={3} />
      </label>
      <button className="primary-button" disabled={status === "creating"} type="submit">
        {status === "creating" ? "Creating..." : "Create Patient"}
      </button>
      {message !== null ? (
        <p className={status === "error" ? "form-message form-message-error" : "form-message"}>
          {message}
        </p>
      ) : null}
    </form>
  );
}
