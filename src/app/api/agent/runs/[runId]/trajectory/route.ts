import { NextResponse } from "next/server";

const RUN_ID_RE = /^[a-zA-Z0-9_-]{1,64}$/;

export async function GET(
  req: Request,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params;
  if (!RUN_ID_RE.test(runId)) {
    return NextResponse.json({ error: "Invalid runId" }, { status: 400 });
  }

  const url = new URL(req.url);
  const afterSeq = url.searchParams.get("after_seq") ?? "0";
  const format = url.searchParams.get("format") === "jsonl" ? "jsonl" : "json";

  const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  const target = `${backendUrl}/v1/agent/runs/${encodeURIComponent(runId)}/trajectory?after_seq=${encodeURIComponent(afterSeq)}&format=${format}`;

  const res = await fetch(target, {
    method: "GET",
    signal: req.signal,
  });

  const headers = new Headers();
  const contentType = res.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const disposition = res.headers.get("content-disposition");
  if (disposition) headers.set("content-disposition", disposition);
  const nosniff = res.headers.get("x-content-type-options");
  if (nosniff) headers.set("x-content-type-options", nosniff);
  headers.set("cache-control", "no-store");

  return new NextResponse(res.body, {
    status: res.status,
    headers,
  });
}
