import { NextResponse } from "next/server";

import { proxyToBackend, readJsonBody } from "@/lib/backend-proxy";

export async function POST(request: Request) {
  const payload = await readJsonBody(request);
  if (payload instanceof NextResponse) {
    return payload;
  }

  return proxyToBackend("/patients", {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}
