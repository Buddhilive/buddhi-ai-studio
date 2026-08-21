"use client";

import { useCallback, useEffect, useState } from "react";

import { parseJsonOrThrow } from "@/lib/fetch-json";
import type { LlmEventSummary } from "@/hooks/use-analytics-events";

export interface LlmEventDetail extends LlmEventSummary {
  input_text: string | null;
  output_text: string | null;
  metadata: Record<string, unknown>;
}

export function useAnalyticsEventDetail(requestId: string | null) {
  const [event, setEvent] = useState<LlmEventDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!requestId) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/analytics/events/${encodeURIComponent(requestId)}`);
      const data = await parseJsonOrThrow<LlmEventDetail>(res);
      setEvent(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load trace";
      console.error("[useAnalyticsEventDetail] fetch failed:", err);
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [requestId]);

  useEffect(() => {
    setEvent(null);
    if (requestId) void refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestId]);

  return { event, isLoading, error, refetch };
}
