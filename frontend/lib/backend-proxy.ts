import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.API_URL_INTERNAL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEFAULT_TIMEOUT_MS = 30_000;

type ProxyOptions = RequestInit & {
  timeoutMs?: number;
};

function errorResponse(status: number, detail: string) {
  return NextResponse.json({ detail }, { status });
}

export async function readJsonBody(request: Request): Promise<unknown | NextResponse> {
  try {
    return await request.json();
  } catch {
    return errorResponse(400, "Request body must be valid JSON.");
  }
}

export async function proxyToBackend(path: string, options: ProxyOptions = {}) {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...init } = options;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      return errorResponse(504, "The MedGraph service took too long to respond. Try again.");
    }
    return errorResponse(502, "The MedGraph service is unavailable. Check that the backend is running.");
  }

  const responseBody = await response.text();
  return new NextResponse(responseBody, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") ?? "application/json",
    },
  });
}
