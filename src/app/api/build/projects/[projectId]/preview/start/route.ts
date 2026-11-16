import { proxyBackendJson } from "@/lib/backend";

export async function POST(
  req: Request,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  const url = new URL(req.url);
  const query = url.search || "";
  return proxyBackendJson(
    `/v1/build/projects/${encodeURIComponent(projectId)}/preview/start${query}`,
    { method: "POST" }
  );
}
