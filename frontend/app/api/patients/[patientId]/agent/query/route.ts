import { NextResponse } from "next/server";

import { proxyToBackend, readJsonBody } from "@/lib/backend-proxy";

type AgentQueryRouteContext = {
  params: Promise<{
    patientId: string;
  }>;
};

export async function POST(request: Request, { params }: AgentQueryRouteContext) {
  const { patientId } = await params;
  const payload = await readJsonBody(request);
  if (payload instanceof NextResponse) {
    return payload;
  }

  return proxyToBackend(`/patients/${encodeURIComponent(patientId)}/agent/query`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
    timeoutMs: 60_000,
  });
}
