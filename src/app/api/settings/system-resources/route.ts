import { proxyBackendJson } from "@/lib/backend";

export async function GET() {
  return proxyBackendJson("/api/settings/system-resources");
}
