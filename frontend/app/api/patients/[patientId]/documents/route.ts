import { NextResponse } from "next/server";

import { proxyToBackend } from "@/lib/backend-proxy";

type UploadRouteContext = {
  params: Promise<{
    patientId: string;
  }>;
};

export async function POST(request: Request, { params }: UploadRouteContext) {
  const { patientId } = await params;

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json({ detail: "Upload must be multipart form data." }, { status: 400 });
  }

  return proxyToBackend(`/patients/${encodeURIComponent(patientId)}/documents`, {
    method: "POST",
    body: formData,
    timeoutMs: 60_000,
  });
}
