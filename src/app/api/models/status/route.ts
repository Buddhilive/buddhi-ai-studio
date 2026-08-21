import { proxyBackendJson } from "@/lib/backend";

export async function GET() {
  return proxyBackendJson("/api/models/status");
}
