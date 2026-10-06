import { proxyBackendJson } from "@/lib/backend";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const url = new URL(req.url);
  const bucket = url.searchParams.get("bucket");
  const query = bucket ? `?bucket=${encodeURIComponent(bucket)}` : "";
  return proxyBackendJson(`/v1/tools/site-crawler/jobs/${id}${query}`);
}
