import { proxyBackendJson } from "@/lib/backend";

export async function POST() {
  return proxyBackendJson("/api/embedding-model/download", { method: "POST" });
}
