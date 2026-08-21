"use client";

import { useCallback, useEffect, useState } from "react";

import { toApiParam, type DateRange } from "@/lib/date-range";
import { parseJsonOrThrow } from "@/lib/fetch-json";

export interface AnalyticsSummary {
  total_requests: number;
  ok_requests: number;
  error_requests: number;
  error_rate: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  streaming_requests: number;
  dropped_events: number;
}

export interface TimeseriesPoint {
  bucket: string;
  value: number;
}

export type MetricKey = "requests" | "tokens" | "latency" | "errors";

const METRICS: MetricKey[] = ["requests", "tokens", "latency", "errors"];

export function useAnalyticsSummary(range: DateRange) {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [timeseries, setTimeseries] = useState<Record<MetricKey, TimeseriesPoint[]> | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const start = toApiParam(range.start);
  const end = toApiParam(range.end);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ start, end });
      const [summaryRes, ...seriesRes] = await Promise.all([
        fetch(`/api/analytics/summary?${params.toString()}`),
        ...METRICS.map((metric) => {
          const p = new URLSearchParams({ start, end, metric });
          return fetch(`/api/analytics/timeseries?${p.toString()}`);
        }),
      ]);

      const summaryData = await parseJsonOrThrow<AnalyticsSummary>(summaryRes);
      const seriesData = await Promise.all(
        seriesRes.map((res) => parseJsonOrThrow<TimeseriesPoint[]>(res))
      );

      setSummary(summaryData);
      setTimeseries(
        METRICS.reduce(
          (acc, metric, index) => ({ ...acc, [metric]: seriesData[index] }),
          {} as Record<MetricKey, TimeseriesPoint[]>
        )
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load analytics";
      console.error("[useAnalyticsSummary] fetch failed:", err);
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [start, end]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { summary, timeseries, isLoading, error, refetch };
}
