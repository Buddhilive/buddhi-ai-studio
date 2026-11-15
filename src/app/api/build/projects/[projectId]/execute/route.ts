import { proxyBackendJson } from "@/lib/backend";

export async function POST(
  req: Request,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  const body = await req.text();
  return proxyBackendJson(`/v1/build/projects/${encodeURIComponent(projectId)}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
}
