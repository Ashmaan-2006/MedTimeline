"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useRef, useState } from "react";

type DocumentUploadFormProps = {
  patientId?: string;
  showPatientIdField?: boolean;
};

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function DocumentUploadForm({
  patientId,
  showPatientIdField = true,
}: DocumentUploadFormProps) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [patientIdInput, setPatientIdInput] = useState("");
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const resolvedPatientId = patientId ?? patientIdInput.trim();
    if (resolvedPatientId.length === 0) {
      setStatus("error");
      setMessage(
        showPatientIdField
          ? "Enter a patient UUID before uploading."
          : "Create a patient before uploading a document.",
      );
      return;
    }

    if (!UUID_PATTERN.test(resolvedPatientId)) {
      setStatus("error");
      setMessage("Enter a valid patient UUID. Create a patient first, then paste its ID here.");
      return;
    }

    const file = fileInputRef.current?.files?.[0];
    if (file === undefined) {
      setStatus("error");
      setMessage("Select a PDF or text document before uploading.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setStatus("uploading");
    setMessage(null);

    const response = await fetch(`/api/patients/${resolvedPatientId}/documents`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      setStatus("error");
      if (response.status === 404) {
        setMessage("No patient exists with that UUID.");
      } else {
        setMessage("Upload failed. Check the backend service and try again.");
      }
      return;
    }

    setStatus("success");
    setMessage("Document uploaded, extracted, summarized, and added to the timeline.");
    if (fileInputRef.current !== null) {
      fileInputRef.current.value = "";
    }
    router.refresh();
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      {patientId === undefined && showPatientIdField ? (
        <div className="patient-id-field">
          <label className="upload-label" htmlFor="upload-patient-id">
            Patient UUID
          </label>
          <input
            className="text-input"
            disabled={status === "uploading"}
            id="upload-patient-id"
            onChange={(event) => setPatientIdInput(event.target.value)}
            placeholder="Paste an existing patient UUID"
            type="text"
            value={patientIdInput}
          />
        </div>
      ) : null}
      <label className="upload-label" htmlFor="patient-document">
        Clinical document
      </label>
      <input
        accept=".pdf,.txt,.text,.md,application/pdf,text/plain,text/markdown"
        className="file-input"
        disabled={status === "uploading"}
        id="patient-document"
        name="file"
        ref={fileInputRef}
        type="file"
      />
      <button className="primary-button" disabled={status === "uploading"} type="submit">
        {status === "uploading" ? "Uploading..." : "Upload Document"}
      </button>
      {message !== null ? (
        <p className={status === "error" ? "form-message form-message-error" : "form-message"}>
          {message}
        </p>
      ) : null}
    </form>
  );
}
