import { proxyBackendJson } from "@/lib/backend";

export async function POST() {
  return proxyBackendJson("/api/embedding-model/download", { method: "POST" });
}

export async function DELETE() {
  return proxyBackendJson("/api/embedding-model/download", { method: "DELETE" });
}
