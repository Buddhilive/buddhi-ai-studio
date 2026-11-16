import { proxyBackendStream } from "@/lib/backend";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "*",
} as const;

async function handlePreview(
  req: Request,
  context: { params: Promise<{ projectId: string; path?: string[] }> }
) {
  const { projectId, path } = await context.params;
  const url = new URL(req.url);
  const subPath = path?.length ? `/${path.map((s) => encodeURIComponent(s)).join("/")}` : "";
  const query = url.search || "";
  const encodedId = encodeURIComponent(projectId);
  const target = `/v1/build/projects/${encodedId}/preview${subPath}${query}`;

  const headers: Record<string, string> = {
    "X-Preview-Prefix": `/api/build/projects/${encodedId}/preview`,
  };
  const init: RequestInit = { method: req.method, headers };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
    const ct = req.headers.get("content-type");
    if (ct) headers["Content-Type"] = ct;
  }
  const upstream = await proxyBackendStream(target, init);
  const respHeaders = new Headers(upstream.headers);
  for (const [k, v] of Object.entries(CORS_HEADERS)) {
    respHeaders.set(k, v);
  }
  return new Response(upstream.body, {
    status: upstream.status,
    headers: respHeaders,
  });
}

export async function OPTIONS() {
  return new Response(null, { status: 204, headers: CORS_HEADERS });
}

export const GET = handlePreview;
export const POST = handlePreview;
export const PUT = handlePreview;
export const PATCH = handlePreview;
export const DELETE = handlePreview;
