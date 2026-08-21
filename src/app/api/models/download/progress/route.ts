import { backendFetch } from "@/lib/backend";

// SSE responses must never be cached/buffered by Next.
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const backendRes = await backendFetch("/api/models/download/progress");

    if (!backendRes.body) {
      throw new Error("Backend returned an empty progress stream");
    }

    return new Response(backendRes.body, {
      status: backendRes.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch (error) {
    console.error("[backend proxy] GET /api/models/download/progress failed:", error);
    return Response.json(
      { error: "Could not reach the backend service. Is it running?" },
      { status: 502 }
    );
  }
}
