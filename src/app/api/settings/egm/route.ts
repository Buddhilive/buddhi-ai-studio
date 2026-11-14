import { NextResponse } from "next/server";

export async function GET() {
  const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${backendUrl}/api/settings/egm`, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to fetch EGM settings" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err: unknown) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

export async function PUT(req: Request) {
  const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  try {
    const body = await req.json();
    const res = await fetch(`${backendUrl}/api/settings/egm`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to update EGM settings" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err: unknown) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
