"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useRef, useState } from "react";

type DocumentUploadFormProps = {
  patientId?: string;
  showPatientIdField?: boolean;
};

type UploadStatus = "idle" | "uploading" | "queued" | "processing" | "success" | "error";

type UploadedDocument = {
  id: string;
  processing_status: DocumentProcessingStatus;
  celery_task_id: string | null;
};

type DocumentProcessingStatus = "uploaded" | "queued" | "processing" | "completed" | "failed";

type DocumentStatusResponse = {
  document_id: string;
  status: DocumentProcessingStatus;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
};

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const POLL_INTERVAL_MS = 2500;
const MAX_POLL_ATTEMPTS = 24;

export function DocumentUploadForm({
  patientId,
  showPatientIdField = true,
}: DocumentUploadFormProps) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [patientIdInput, setPatientIdInput] = useState("");
  const [status, setStatus] = useState<UploadStatus>("idle");
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

    let uploadedDocument: UploadedDocument;
    try {
      uploadedDocument = (await response.json()) as UploadedDocument;
    } catch {
      setStatus("error");
      setMessage("Upload succeeded, but the response could not be read.");
      return;
    }

    setStatus("queued");
    setMessage("Queued for processing...");
    if (fileInputRef.current !== null) {
      fileInputRef.current.value = "";
    }

    await pollDocumentStatus(resolvedPatientId, uploadedDocument.id);
  }

  async function pollDocumentStatus(resolvedPatientId: string, documentId: string) {
    for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
      if (attempt > 0) {
        await wait(POLL_INTERVAL_MS);
      }

      const response = await fetch(
        `/api/patients/${resolvedPatientId}/documents/${documentId}/status`,
      );

      if (!response.ok) {
        setStatus("error");
        setMessage(
          `Document was uploaded, but status polling failed with ${response.status}. Refreshing the document list.`,
        );
        router.refresh();
        return;
      }

      let documentStatus: DocumentStatusResponse;
      try {
        documentStatus = (await response.json()) as DocumentStatusResponse;
      } catch {
        setStatus("error");
        setMessage("Document was uploaded, but the processing status response could not be read.");
        router.refresh();
        return;
      }

      if (documentStatus.status === "queued" || documentStatus.status === "uploaded") {
        setStatus("queued");
        setMessage("Queued for processing...");
        continue;
      }

      if (documentStatus.status === "processing") {
        setStatus("processing");
        setMessage("Processing document...");
        continue;
      }

      if (documentStatus.status === "completed") {
        setStatus("success");
        setMessage("Document processed and added to the timeline.");
        router.refresh();
        return;
      }

      if (documentStatus.status === "failed") {
        setStatus("error");
        setMessage(documentStatus.error ?? "Document processing failed.");
        router.refresh();
        return;
      }
    }

    setStatus("success");
    setMessage("Document is still processing. Refresh the page in a moment to check progress.");
    router.refresh();
  }

  function wait(milliseconds: number) {
    return new Promise((resolve) => {
      window.setTimeout(resolve, milliseconds);
    });
  }

  const isBusy = status === "uploading" || status === "queued" || status === "processing";

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      {patientId === undefined && showPatientIdField ? (
        <div className="patient-id-field">
          <label className="upload-label" htmlFor="upload-patient-id">
            Patient UUID
          </label>
          <input
            className="text-input"
            disabled={isBusy}
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
        disabled={isBusy}
        id="patient-document"
        name="file"
        ref={fileInputRef}
        type="file"
      />
      <button className="primary-button" disabled={isBusy} type="submit">
        {status === "uploading"
          ? "Uploading..."
          : status === "queued"
            ? "Queued..."
            : status === "processing"
              ? "Processing..."
              : "Upload Document"}
      </button>
      {message !== null ? (
        <p className={status === "error" ? "form-message form-message-error" : "form-message"}>
          {message}
        </p>
      ) : null}
    </form>
  );
}
