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
      return NextResponse.json({ error: "Failed to fetch experiences" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json({ experiences: data.experiences ?? [] });
  } catch (err: unknown) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

export async function PATCH(req: Request) {
  const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  try {
    const body = await req.json();
    const workspaceId = String(body?.workspaceId ?? "default");
    const entryId = String(body?.entryId ?? "");
    const res = await fetch(
      `${backendUrl}/v1/agent/harness/${encodeURIComponent(workspaceId)}/experience/${encodeURIComponent(entryId)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pinned: Boolean(body?.pinned) }),
      }
    );
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to update experience pin" }, { status: res.status });
    }
    return NextResponse.json(await res.json());
  } catch (err: unknown) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

export async function DELETE(req: Request) {
  const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  const { searchParams } = new URL(req.url);
  const workspaceId = searchParams.get("workspaceId") ?? "default";
  const entryId = searchParams.get("entryId") ?? "";
  try {
    const res = await fetch(
      `${backendUrl}/v1/agent/harness/${encodeURIComponent(workspaceId)}/experience/${encodeURIComponent(entryId)}`,
      { method: "DELETE" }
    );
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to delete experience" }, { status: res.status });
    }
    return NextResponse.json(await res.json());
  } catch (err: unknown) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
