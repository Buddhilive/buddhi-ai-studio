import { proxyBackendJson } from "@/lib/backend";

export async function GET(request: Request) {
  const { search } = new URL(request.url);
  return proxyBackendJson(`/api/analytics/summary${search}`);
}
