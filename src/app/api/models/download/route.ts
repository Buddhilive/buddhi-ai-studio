import { proxyBackendJson } from "@/lib/backend";

export async function POST() {
  return proxyBackendJson("/api/models/download", { method: "POST" });
}

export async function DELETE() {
  return proxyBackendJson("/api/models/download", { method: "DELETE" });
}
