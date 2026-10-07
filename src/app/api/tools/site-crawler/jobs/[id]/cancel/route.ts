import { proxyBackendJson } from "@/lib/backend";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyBackendJson(`/v1/tools/site-crawler/jobs/${id}/cancel`, {
    method: "POST",
  });
}
