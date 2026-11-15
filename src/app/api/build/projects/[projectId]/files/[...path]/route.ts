import { proxyBackendJson } from "@/lib/backend";

export async function GET(
  _req: Request,
  context: { params: Promise<{ projectId: string; path: string[] }> }
) {
  const { projectId, path } = await context.params;
  const relPath = path.map((seg) => encodeURIComponent(seg)).join("/");
  return proxyBackendJson(
    `/v1/build/projects/${encodeURIComponent(projectId)}/files/${relPath}`
  );
}
