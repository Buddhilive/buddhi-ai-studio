"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type EmbeddingModelStatus = "not_downloaded" | "downloading" | "ready" | "error";

export interface EmbeddingModelStatusResponse {
  model_id: string;
  repo_id: string;
  status: EmbeddingModelStatus;
  error: string | null;
}

const POLL_INTERVAL_MS = 2000;

async function parseJsonOrThrow<T>(res: Response): Promise<T> {
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

export function useEmbeddingModelStatus() {
  const [state, setState] = useState<EmbeddingModelStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const fetchStatus = useCallback(async (): Promise<EmbeddingModelStatusResponse | null> => {
    try {
      const res = await fetch("/api/embedding-model/status");
      const data = await parseJsonOrThrow<EmbeddingModelStatusResponse>(res);
      setState(data);
      setFetchError(null);
      return data;
    } catch (err) {
      console.error("[useEmbeddingModelStatus] status fetch failed:", err);
      setFetchError(err instanceof Error ? err.message : "Failed to load embedding model status");
      return null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setIsLoading(true);
      await fetchStatus();
      if (!cancelled) setIsLoading(false);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const status = state?.status ?? "not_downloaded";

  useEffect(() => {
    if (status !== "downloading") {
      stopPolling();
      return;
    }
    if (!pollTimerRef.current) {
      pollTimerRef.current = setInterval(() => void fetchStatus(), POLL_INTERVAL_MS);
    }
    return stopPolling;
  }, [status, fetchStatus, stopPolling]);

  const startDownload = useCallback(async () => {
    try {
      const res = await fetch("/api/embedding-model/download", { method: "POST" });
      const data = await parseJsonOrThrow<EmbeddingModelStatusResponse>(res);
      setState(data);
      setFetchError(null);
    } catch (err) {
      console.error("[useEmbeddingModelStatus] download trigger failed:", err);
      setFetchError(err instanceof Error ? err.message : "Failed to start download");
    }
  }, []);

  return {
    modelId: state?.model_id ?? null,
    repoId: state?.repo_id ?? null,
    status,
    error: state?.error ?? fetchError,
    isLoading,
    startDownload,
  };
}
