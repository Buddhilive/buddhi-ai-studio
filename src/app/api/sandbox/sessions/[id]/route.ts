import { proxyBackendJson } from "@/lib/backend";

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyBackendJson(`/v1/sandbox/sessions/${id}`, {
    method: "DELETE",
  });
}
