export async function parseJsonOrThrow<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const message =
      data && typeof data === "object" && typeof data.error === "string"
        ? data.error
        : data && typeof data === "object" && typeof data.detail === "string"
          ? data.detail
          : `Request failed with status ${res.status}`;
    throw new Error(message);
  }
  return data as T;
}
