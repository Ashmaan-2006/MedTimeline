import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.API_URL_INTERNAL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RagQueryRouteContext = {
  params: Promise<{
    patientId: string;
  }>;
};

export async function POST(request: Request, { params }: RagQueryRouteContext) {
  const { patientId } = await params;
  const payload = await request.json();

  const response = await fetch(
    `${API_BASE_URL}/patients/${encodeURIComponent(patientId)}/rag/query`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
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
