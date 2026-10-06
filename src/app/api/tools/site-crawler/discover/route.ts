import { proxyBackendJson } from "@/lib/backend";

export async function POST(req: Request) {
  const body = await req.text();
  return proxyBackendJson("/v1/tools/site-crawler/discover", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
}
