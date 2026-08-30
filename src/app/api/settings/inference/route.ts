import { proxyBackendJson } from "@/lib/backend";

export async function GET() {
  return proxyBackendJson("/api/settings/inference");
}

export async function PUT(req: Request) {
  const body = await req.text();
  return proxyBackendJson("/api/settings/inference", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
  });
}
