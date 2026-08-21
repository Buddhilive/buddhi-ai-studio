import { proxyBackendJson } from "@/lib/backend";

export async function GET() {
  return proxyBackendJson("/api/settings/hf-token");
}

export async function PUT(req: Request) {
  const body = await req.text();
  return proxyBackendJson("/api/settings/hf-token", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
  });
}

export async function DELETE() {
  return proxyBackendJson("/api/settings/hf-token", { method: "DELETE" });
}
