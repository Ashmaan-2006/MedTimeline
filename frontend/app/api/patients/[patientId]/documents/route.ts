import { NextResponse } from "next/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type UploadRouteContext = {
  params: Promise<{
    patientId: string;
  }>;
};

export async function POST(request: Request, { params }: UploadRouteContext) {
  const { patientId } = await params;
  const formData = await request.formData();

  const response = await fetch(
    `${API_BASE_URL}/patients/${encodeURIComponent(patientId)}/documents`,
    {
      method: "POST",
      body: formData,
    },
  );

  const responseBody = await response.text();

  return new NextResponse(responseBody, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") ?? "application/json",
    },
  });
}

