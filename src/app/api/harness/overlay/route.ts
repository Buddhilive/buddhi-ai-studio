import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  const { searchParams } = new URL(req.url);
  const workspaceId = searchParams.get("workspaceId") ?? "default";
  try {
    const res = await fetch(`${backendUrl}/v1/agent/harness/${encodeURIComponent(workspaceId)}`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to fetch harness overlay" }, { status: res.status });
    }
    return NextResponse.json(await res.json());
  } catch (err: unknown) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

export async function POST(req: Request) {
  const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  try {
    const body = await req.json();
    const workspaceId = String(body?.workspaceId ?? "default");
    const action = body?.action === "reset" ? "reset" : "rollback";
    const endpoint =
      action === "reset"
        ? `${backendUrl}/v1/agent/harness/${encodeURIComponent(workspaceId)}/reset`
        : `${backendUrl}/v1/agent/harness/${encodeURIComponent(workspaceId)}/rollback`;
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: action === "reset" ? undefined : JSON.stringify({ version_id: body?.versionId }),
    });
    if (!res.ok) {
      return NextResponse.json({ error: `Failed to ${action} harness overlay` }, { status: res.status });
    }
    return NextResponse.json(await res.json());
  } catch (err: unknown) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
