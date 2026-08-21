import { proxyBackendJson } from "@/lib/backend";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ modelId: string }> }
) {
  const { modelId } = await params;
  return proxyBackendJson(`/api/models/${modelId}/download`, { method: "POST" });
}

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ modelId: string }> }
) {
  const { modelId } = await params;
  return proxyBackendJson(`/api/models/${modelId}/download`, { method: "DELETE" });
}
