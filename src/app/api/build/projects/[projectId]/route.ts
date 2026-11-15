import { proxyBackendJson } from "@/lib/backend";

export async function GET(
  _req: Request,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  return proxyBackendJson(`/v1/build/projects/${encodeURIComponent(projectId)}`);
}

export async function DELETE(
  _req: Request,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  return proxyBackendJson(`/v1/build/projects/${encodeURIComponent(projectId)}`, {
    method: "DELETE",
  });
}
