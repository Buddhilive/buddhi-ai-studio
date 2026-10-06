import { proxyBackendJson } from "@/lib/backend";

export async function GET() {
  return proxyBackendJson("/v1/tools/site-crawler/health");
}
