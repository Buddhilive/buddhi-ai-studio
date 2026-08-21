"use client";

import { useCallback, useEffect, useState } from "react";

import { toApiParam, type DateRange } from "@/lib/date-range";
import { parseJsonOrThrow } from "@/lib/fetch-json";

export interface LlmEventSummary {
  request_id: string;
  ts: string;
  model_name: string;
  endpoint: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
  status: "ok" | "error";
  error_message: string | null;
  stream: boolean;
  client_id: string | null;
}

export interface EventsPage {
  items: LlmEventSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface EventsFilters {
  status?: "ok" | "error";
  model?: string;
  search?: string;
}

const PAGE_SIZE = 25;

export function useAnalyticsEvents(range: DateRange, filters: EventsFilters) {
  const [page, setPage] = useState<EventsPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const start = toApiParam(range.start);
  const end = toApiParam(range.end);
  const { status, model, search } = filters;

  useEffect(() => {
    setOffset(0);
  }, [start, end, status, model, search]);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        start,
        end,
        limit: String(PAGE_SIZE),
        offset: String(offset),
      });
      if (status) params.set("status", status);
      if (model) params.set("model", model);
      if (search) params.set("search", search);

      const res = await fetch(`/api/analytics/events?${params.toString()}`);
      const data = await parseJsonOrThrow<EventsPage>(res);
      setPage(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load traces";
      console.error("[useAnalyticsEvents] fetch failed:", err);
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [start, end, status, model, search, offset]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  const nextPage = useCallback(() => {
    setOffset((prev) => (page && prev + PAGE_SIZE < page.total ? prev + PAGE_SIZE : prev));
  }, [page]);

  const prevPage = useCallback(() => {
    setOffset((prev) => Math.max(0, prev - PAGE_SIZE));
  }, []);

  return {
    page,
    offset,
    pageSize: PAGE_SIZE,
    isLoading,
    error,
    refetch,
    nextPage,
    prevPage,
    hasNext: page ? offset + PAGE_SIZE < page.total : false,
    hasPrev: offset > 0,
  };
}
