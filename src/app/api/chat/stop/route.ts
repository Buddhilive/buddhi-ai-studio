import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const { runId } = await req.json();
    if (!runId) {
      return NextResponse.json({ error: "runId required" }, { status: 400 });
    }

    const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
    const res = await fetch(`${backendUrl}/v1/agent/runs/${runId}`, {
      method: "DELETE",
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
