import { proxyBackendJson } from "@/lib/backend";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ slug: string; hash: string }> }
) {
  const { slug, hash } = await params;
  const url = new URL(req.url);
  const bucket = url.searchParams.get("bucket");
  const query = bucket ? `?bucket=${encodeURIComponent(bucket)}` : "";
  return proxyBackendJson(`/v1/tools/site-crawler/projects/${slug}/pages/${hash}${query}`);
}
