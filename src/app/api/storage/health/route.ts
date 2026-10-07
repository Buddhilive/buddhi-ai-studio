import { proxyBackendJson } from "@/lib/backend";

export async function GET() {
  return proxyBackendJson("/v1/storage/health");
}
