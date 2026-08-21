"use client";

import { useState } from "react";

import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DateRangePicker } from "@/components/analytics/date-range-picker";
import { EventsTable } from "@/components/analytics/events-table";
import { TraceSheet } from "@/components/analytics/trace-sheet";
import { useAnalyticsEvents, type EventsFilters } from "@/hooks/use-analytics-events";
import { presetToRange, type DateRange } from "@/lib/date-range";

export default function TracesPage() {
  const [range, setRange] = useState<DateRange>(() => presetToRange("7d"));
  const [status, setStatus] = useState<EventsFilters["status"] | "all">("all");
  const [search, setSearch] = useState("");
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);

  const eventsState = useAnalyticsEvents(range, {
    status: status === "all" ? undefined : status,
    search: search || undefined,
  });

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Traces</h1>
          <p className="text-muted-foreground text-sm">
            Every chat completion call, in order.
          </p>
        </div>
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search by request ID or model"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <Select value={status} onValueChange={(v) => setStatus(v as typeof status)}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="ok">OK</SelectItem>
            <SelectItem value="error">Error</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <EventsTable
        page={eventsState.page}
        isLoading={eventsState.isLoading}
        error={eventsState.error}
        onRowClick={(event) => setSelectedRequestId(event.request_id)}
        onRetry={() => void eventsState.refetch()}
        hasNext={eventsState.hasNext}
        hasPrev={eventsState.hasPrev}
        onNext={eventsState.nextPage}
        onPrev={eventsState.prevPage}
      />

      <TraceSheet
        requestId={selectedRequestId}
        onOpenChange={(open) => !open && setSelectedRequestId(null)}
      />
    </div>
  );
}
