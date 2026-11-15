import { proxyBackendStream } from "@/lib/backend";

async function handlePreview(
  req: Request,
  context: { params: Promise<{ projectId: string; path?: string[] }> }
) {
  const { projectId, path } = await context.params;
  const url = new URL(req.url);
  const subPath = path?.length ? `/${path.map((s) => encodeURIComponent(s)).join("/")}` : "";
  const query = url.search || "";
  const target = `/v1/build/projects/${encodeURIComponent(projectId)}/preview${subPath}${query}`;

  const init: RequestInit = { method: req.method };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
    const ct = req.headers.get("content-type");
    if (ct) init.headers = { "Content-Type": ct };
  }
  return proxyBackendStream(target, init);
}

export const GET = handlePreview;
export const POST = handlePreview;
export const PUT = handlePreview;
export const PATCH = handlePreview;
export const DELETE = handlePreview;
