import { proxyBackendJson } from "@/lib/backend";

export async function POST() {
  return proxyBackendJson("/api/models/download/pause", { method: "POST" });
}
