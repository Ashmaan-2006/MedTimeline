import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.API_URL_INTERNAL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type StatusRouteContext = {
  params: Promise<{
    patientId: string;
    documentId: string;
  }>;
};

export async function GET(_request: Request, { params }: StatusRouteContext) {
  const { patientId, documentId } = await params;

  const response = await fetch(
    `${API_BASE_URL}/patients/${encodeURIComponent(patientId)}/documents/${encodeURIComponent(
      documentId,
    )}/status`,
    {
      cache: "no-store",
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
