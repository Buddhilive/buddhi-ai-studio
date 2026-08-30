"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type EmbeddingModelStatus =
  | "not_downloaded"
  | "downloading"
  | "paused"
  | "ready"
  | "error";

export interface ModelDownloadComponentState {
  model_id: string;
  status: "idle" | "downloading" | "paused" | "completed" | "failed";
  repo_id: string;
  filename: string;
  downloaded_bytes: number;
  total_bytes: number | null;
  percentage: number;
  error: string | null;
  updated_at: string;
}

export interface EmbeddingModelStatusResponse {
  model_id: string;
  repo_id: string;
  status: EmbeddingModelStatus;
  error: string | null;
  downloaded_bytes: number;
  total_bytes: number | null;
  percentage: number;
  current_phase: string | null;
  files?: Record<string, ModelDownloadComponentState>;
}

const POLL_INTERVAL_ACTIVE_MS = 1000;

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
  }, [fetchStatus]);

  const status = state?.status ?? "not_downloaded";

  useEffect(() => {
    if (status !== "downloading") {
      stopPolling();
      return;
    }
    if (!pollTimerRef.current) {
      pollTimerRef.current = setInterval(() => void fetchStatus(), POLL_INTERVAL_ACTIVE_MS);
    }
    return stopPolling;
  }, [status, fetchStatus, stopPolling]);

  const executeAction = useCallback(
    async (url: string, method: "POST" | "DELETE", errorFallback: string) => {
      try {
        const res = await fetch(url, { method });
        const data = await parseJsonOrThrow<EmbeddingModelStatusResponse>(res);
        setState(data);
        setFetchError(null);
      } catch (err) {
        console.error(`[useEmbeddingModelStatus] ${method} ${url} failed:`, err);
        setFetchError(err instanceof Error ? err.message : errorFallback);
      }
    },
    []
  );

  const startDownload = useCallback(
    () => executeAction("/api/embedding-model/download", "POST", "Failed to start download"),
    [executeAction]
  );

  const pauseDownload = useCallback(
    () => executeAction("/api/embedding-model/download/pause", "POST", "Failed to pause download"),
    [executeAction]
  );

  const resumeDownload = useCallback(
    () => executeAction("/api/embedding-model/download/resume", "POST", "Failed to resume download"),
    [executeAction]
  );

  const cancelDownload = useCallback(
    () => executeAction("/api/embedding-model/download", "DELETE", "Failed to cancel download"),
    [executeAction]
  );

  return {
    modelId: state?.model_id ?? null,
    repoId: state?.repo_id ?? null,
    status,
    error: state?.error ?? fetchError,
    downloadedBytes: state?.downloaded_bytes ?? 0,
    totalBytes: state?.total_bytes ?? null,
    percentage: state?.percentage ?? 0,
    currentPhase: state?.current_phase ?? null,
    files: state?.files,
    isLoading,
    startDownload,
    pauseDownload,
    resumeDownload,
    cancelDownload,
    refresh: fetchStatus,
  };
}
