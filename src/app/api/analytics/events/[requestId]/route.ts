import { proxyBackendJson } from "@/lib/backend";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ requestId: string }> }
) {
  const { requestId } = await params;
  return proxyBackendJson(`/api/analytics/events/${encodeURIComponent(requestId)}`);
}
