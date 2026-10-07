import { proxyBackendJson } from "@/lib/backend";

export async function POST(req: Request) {
  const body = await req.text();
  return proxyBackendJson("/v1/crawl", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
}

export async function GET() {
  return proxyBackendJson("/v1/crawl/health", {
    method: "GET",
  });
}
