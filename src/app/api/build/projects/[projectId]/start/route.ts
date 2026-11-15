import { proxyBackendJson } from "@/lib/backend";

export async function POST(
  _req: Request,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  return proxyBackendJson(`/v1/build/projects/${encodeURIComponent(projectId)}/start`, {
    method: "POST",
  });
}
