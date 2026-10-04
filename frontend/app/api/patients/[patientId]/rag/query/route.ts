import { NextResponse } from "next/server";

import { proxyToBackend, readJsonBody } from "@/lib/backend-proxy";

type RagQueryRouteContext = {
  params: Promise<{
    patientId: string;
  }>;
};

export async function POST(request: Request, { params }: RagQueryRouteContext) {
  const { patientId } = await params;
  const payload = await readJsonBody(request);
  if (payload instanceof NextResponse) {
    return payload;
  }

  return proxyToBackend(`/patients/${encodeURIComponent(patientId)}/rag/query`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}
