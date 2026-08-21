import { proxyBackendJson } from "@/lib/backend";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ modelId: string }> }
) {
  const { modelId } = await params;
  return proxyBackendJson(`/api/models/${modelId}/availability`);
}
