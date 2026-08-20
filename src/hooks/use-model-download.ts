"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type DownloadStatus = "idle" | "downloading" | "paused" | "completed" | "failed";

export interface ModelDownloadState {
  status: DownloadStatus;
  repo_id: string;
  filename: string;
  downloaded_bytes: number;
  total_bytes: number | null;
  percentage: number;
  error: string | null;
  updated_at: string;
}

export interface ModelAvailability {
  available: boolean;
  path: string | null;
  size_bytes: number | null;
}

const TERMINAL_STATUSES: DownloadStatus[] = ["completed", "failed", "idle"];
const POLL_INTERVAL_MS = 3000;

function isTerminal(status: DownloadStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

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

export function useModelDownload() {
  const [state, setState] = useState<ModelDownloadState | null>(null);
  const [availability, setAvailability] = useState<ModelAvailability | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const closeStream = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
  }, []);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const fetchStatus = useCallback(async (): Promise<ModelDownloadState | null> => {
    try {
      const res = await fetch("/api/models/download/status");
      const data = await parseJsonOrThrow<ModelDownloadState>(res);
      setState(data);
      setError(null);
      return data;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load download status";
      console.error("[useModelDownload] status fetch failed:", err);
      setError(message);
      return null;
    }
  }, []);

  const fetchAvailability = useCallback(async () => {
    try {
      const res = await fetch("/api/models/availability");
      const data = await parseJsonOrThrow<ModelAvailability>(res);
      setAvailability(data);
    } catch (err) {
      console.error("[useModelDownload] availability fetch failed:", err);
    }
  }, []);

  const startPolling = useCallback(() => {
    stopPolling();
    pollTimerRef.current = setInterval(() => {
      void fetchStatus();
    }, POLL_INTERVAL_MS);
  }, [fetchStatus, stopPolling]);

  const openStream = useCallback(() => {
    closeStream();
    const es = new EventSource("/api/models/download/progress");
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ModelDownloadState;
        setState(data);
        setError(null);
        if (isTerminal(data.status)) {
          closeStream();
          stopPolling();
          void fetchAvailability();
        }
      } catch (err) {
        console.error("[useModelDownload] failed to parse progress event:", err);
      }
    };

    es.onerror = (event) => {
      console.error("[useModelDownload] SSE connection error, falling back to polling:", event);
      closeStream();
      startPolling();
    };
  }, [closeStream, fetchAvailability, startPolling, stopPolling]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setIsLoading(true);
      const [current] = await Promise.all([fetchStatus(), fetchAvailability()]);
      if (cancelled) return;
      setIsLoading(false);
      if (current && !isTerminal(current.status)) {
        openStream();
      }
    })();

    return () => {
      cancelled = true;
      closeStream();
      stopPolling();
    };
    // Intentionally run once on mount: this hook re-syncs from the backend
    // (the source of truth) every time the page mounts, which is what makes
    // progress survive navigating away and back.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runAction = useCallback(
    async (path: string, method: "POST" | "DELETE"): Promise<ModelDownloadState | null> => {
      try {
        const res = await fetch(path, { method });
        const data = await parseJsonOrThrow<ModelDownloadState>(res);
        setState(data);
        setError(null);
        if (isTerminal(data.status)) {
          closeStream();
          stopPolling();
          void fetchAvailability();
        } else {
          openStream();
        }
        return data;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Action failed";
        console.error(`[useModelDownload] ${method} ${path} failed:`, err);
        setError(message);
        return null;
      }
    },
    [closeStream, fetchAvailability, openStream, stopPolling]
  );

  const start = useCallback(() => runAction("/api/models/download", "POST"), [runAction]);
  const pause = useCallback(() => runAction("/api/models/download/pause", "POST"), [runAction]);
  const resume = useCallback(() => runAction("/api/models/download/resume", "POST"), [runAction]);
  const cancel = useCallback(() => runAction("/api/models/download", "DELETE"), [runAction]);

  return { state, availability, isLoading, error, start, pause, resume, cancel };
}
