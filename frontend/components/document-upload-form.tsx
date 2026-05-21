"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useRef, useState } from "react";

type DocumentUploadFormProps = {
  patientId: string;
};

export function DocumentUploadForm({ patientId }: DocumentUploadFormProps) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

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

    const response = await fetch(`/api/patients/${patientId}/documents`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      setStatus("error");
      setMessage("Upload failed. Check the backend service and try again.");
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

