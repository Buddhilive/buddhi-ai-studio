import { proxyBackendStream } from "@/lib/backend";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params;
  const url = new URL(req.url);
  const bucket = url.searchParams.get("bucket");
  const query = bucket ? `?bucket=${encodeURIComponent(bucket)}` : "";
  return proxyBackendStream(`/v1/tools/site-crawler/projects/${slug}/zip${query}`);
}
