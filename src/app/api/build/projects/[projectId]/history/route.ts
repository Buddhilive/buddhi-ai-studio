import { proxyBackendJson } from "@/lib/backend";

export async function GET(
  _req: Request,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  return proxyBackendJson(`/v1/build/projects/${encodeURIComponent(projectId)}/history`);
}

export async function PUT(
  req: Request,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  const body = await req.text();
  return proxyBackendJson(`/v1/build/projects/${encodeURIComponent(projectId)}/history`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
  });
}
