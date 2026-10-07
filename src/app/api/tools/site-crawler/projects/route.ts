import { proxyBackendJson } from "@/lib/backend";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const bucket = url.searchParams.get("bucket");
  const query = bucket ? `?bucket=${encodeURIComponent(bucket)}` : "";
  return proxyBackendJson(`/v1/tools/site-crawler/projects${query}`);
}
