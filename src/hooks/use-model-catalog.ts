"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type ModelCategory = "llm" | "embedding";

export type DownloadStatus = "idle" | "downloading" | "paused" | "completed" | "failed";

export interface ModelCatalogEntry {
  id: string;
  category: ModelCategory;
  name: string;
  repo_id: string;
  filename: string;
  size_bytes: number | null;
}

export interface ModelDownloadState {
  model_id: string;
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
  model_id: string;
  available: boolean;
  path: string | null;
  size_bytes: number | null;
}

const POLL_INTERVAL_MS = 3000;

function isAnyDownloading(states: Record<string, ModelDownloadState>): boolean {
  return Object.values(states).some((s) => s.status === "downloading");
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

function statesToRecord(states: ModelDownloadState[]): Record<string, ModelDownloadState> {
  const record: Record<string, ModelDownloadState> = {};
  for (const state of states) {
    record[state.model_id] = state;
  }
  return record;
}

export function useModelCatalog() {
  const [catalog, setCatalog] = useState<ModelCatalogEntry[]>([]);
  const [states, setStates] = useState<Record<string, ModelDownloadState>>({});
  const [availability, setAvailability] = useState<Record<string, ModelAvailability>>({});
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

  const fetchCatalog = useCallback(async (): Promise<ModelCatalogEntry[]> => {
    try {
      const res = await fetch("/api/models/catalog");
      const data = await parseJsonOrThrow<ModelCatalogEntry[]>(res);
      setCatalog(data);
      return data;
    } catch (err) {
      console.error("[useModelCatalog] catalog fetch failed:", err);
      setError(err instanceof Error ? err.message : "Failed to load model catalog");
      return [];
    }
  }, []);

  const fetchStatus = useCallback(async (): Promise<Record<string, ModelDownloadState> | null> => {
    try {
      const res = await fetch("/api/models/status");
      const data = await parseJsonOrThrow<ModelDownloadState[]>(res);
      const record = statesToRecord(data);
      setStates(record);
      setError(null);
      return record;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load download status";
      console.error("[useModelCatalog] status fetch failed:", err);
      setError(message);
      return null;
    }
  }, []);

  const fetchAvailability = useCallback(async (entries: ModelCatalogEntry[]) => {
    try {
      const results = await Promise.all(
        entries.map(async (entry) => {
          const res = await fetch(`/api/models/${entry.id}/availability`);
          return parseJsonOrThrow<ModelAvailability>(res);
        })
      );
      const record: Record<string, ModelAvailability> = {};
      for (const item of results) {
        record[item.model_id] = item;
      }
      setAvailability(record);
    } catch (err) {
      console.error("[useModelCatalog] availability fetch failed:", err);
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
        const data = JSON.parse(event.data) as ModelDownloadState[];
        const record = statesToRecord(data);
        setStates(record);
        setError(null);
        if (!isAnyDownloading(record)) {
          closeStream();
          stopPolling();
          void fetchCatalog().then((entries) => fetchAvailability(entries));
        }
      } catch (err) {
        console.error("[useModelCatalog] failed to parse progress event:", err);
      }
    };

    es.onerror = (event) => {
      console.error("[useModelCatalog] SSE connection error, falling back to polling:", event);
      closeStream();
      startPolling();
    };
  }, [closeStream, fetchAvailability, fetchCatalog, startPolling, stopPolling]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setIsLoading(true);
      const entries = await fetchCatalog();
      const currentStates = await fetchStatus();
      if (cancelled) return;
      await fetchAvailability(entries);
      if (cancelled) return;
      setIsLoading(false);
      if (currentStates && isAnyDownloading(currentStates)) {
        openStream();
      }
    })();

    return () => {
      cancelled = true;
      closeStream();
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runAction = useCallback(
    async (path: string, method: "POST" | "DELETE"): Promise<ModelDownloadState | null> => {
      try {
        const res = await fetch(path, { method });
        const data = await parseJsonOrThrow<ModelDownloadState>(res);
        setStates((prev) => ({ ...prev, [data.model_id]: data }));
        setError(null);
        if (data.status === "downloading") {
          openStream();
        } else {
          closeStream();
          stopPolling();
          void fetchCatalog().then((entries) => fetchAvailability(entries));
        }
        return data;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Action failed";
        console.error(`[useModelCatalog] ${method} ${path} failed:`, err);
        setError(message);
        return null;
      }
    },
    [closeStream, fetchAvailability, fetchCatalog, openStream, stopPolling]
  );

  const start = useCallback(
    (modelId: string) => runAction(`/api/models/${modelId}/download`, "POST"),
    [runAction]
  );
  const pause = useCallback(
    (modelId: string) => runAction(`/api/models/${modelId}/download/pause`, "POST"),
    [runAction]
  );
  const resume = useCallback(
    (modelId: string) => runAction(`/api/models/${modelId}/download/resume`, "POST"),
    [runAction]
  );
  const cancel = useCallback(
    (modelId: string) => runAction(`/api/models/${modelId}/download`, "DELETE"),
    [runAction]
  );

  return { catalog, states, availability, isLoading, error, start, pause, resume, cancel };
}
