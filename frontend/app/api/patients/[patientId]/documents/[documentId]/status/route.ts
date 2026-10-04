import { proxyToBackend } from "@/lib/backend-proxy";

type StatusRouteContext = {
  params: Promise<{
    patientId: string;
    documentId: string;
  }>;
};

export async function GET(_request: Request, { params }: StatusRouteContext) {
  const { patientId, documentId } = await params;

  return proxyToBackend(
    `/patients/${encodeURIComponent(patientId)}/documents/${encodeURIComponent(documentId)}/status`,
    {
      cache: "no-store",
      timeoutMs: 10_000,
    },
  );
}
