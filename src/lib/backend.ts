const BACKEND_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

export class BackendUnreachableError extends Error {
  constructor(cause: unknown) {
    super("Could not reach the backend service");
    this.cause = cause;
  }
}

/**
 * Fetches a path on the FastAPI backend. Network-level failures (backend not
 * running, DNS, etc.) are normalized to `BackendUnreachableError` so callers
 * can distinguish "backend is down" from a normal non-2xx response.
 */
export async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${BACKEND_URL}${path}`, init);
  } catch (error) {
    throw new BackendUnreachableError(error);
  }
}

/**
 * Proxies a simple JSON backend endpoint: forwards the backend's status code
 * and JSON body verbatim (so 409/500 responses reach the client unchanged),
 * and turns backend-unreachable into a 502 with a clear message. Logs every
 * failure server-side.
 */
export async function proxyBackendJson(path: string, init?: RequestInit): Promise<Response> {
  try {
    const backendRes = await backendFetch(path, init);
    const body = await backendRes.text();
    return new Response(body, {
      status: backendRes.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error(`[backend proxy] ${init?.method ?? "GET"} ${path} failed:`, error);
    return Response.json(
      { error: "Could not reach the backend service. Is it running?" },
      { status: 502 }
    );
  }
}
