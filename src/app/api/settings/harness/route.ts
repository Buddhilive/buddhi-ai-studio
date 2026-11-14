import { NextResponse } from "next/server";

export async function GET() {
  const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${backendUrl}/api/settings/harness`, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to fetch Harness2 settings" }, { status: res.status });
    }
    return NextResponse.json(await res.json());
  } catch (err: unknown) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

export async function PUT(req: Request) {
  const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  try {
    const body = await req.json();
    const res = await fetch(`${backendUrl}/api/settings/harness`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to update Harness2 settings" }, { status: res.status });
    }
    return NextResponse.json(await res.json());
  } catch (err: unknown) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
