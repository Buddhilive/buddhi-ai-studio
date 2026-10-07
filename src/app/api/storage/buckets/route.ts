import { proxyBackendJson } from "@/lib/backend";

export async function GET() {
  return proxyBackendJson("/v1/storage/buckets");
}

export async function POST(req: Request) {
  const body = await req.text();
  return proxyBackendJson("/v1/storage/buckets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
}
