"use client";

import { useState } from "react";
import { AlertTriangleIcon } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DateRangePicker } from "@/components/analytics/date-range-picker";
import { MetricChart } from "@/components/analytics/metric-chart";
import { EventsTable } from "@/components/analytics/events-table";
import { TraceSheet } from "@/components/analytics/trace-sheet";
import { useAnalyticsSummary } from "@/hooks/use-analytics-summary";
import { useAnalyticsEvents } from "@/hooks/use-analytics-events";
import { presetToRange, type DateRange } from "@/lib/date-range";

export default function ErrorsPage() {
  const [range, setRange] = useState<DateRange>(() => presetToRange("7d"));
  const { timeseries, isLoading: seriesLoading, error: seriesError, refetch } =
    useAnalyticsSummary(range);
  const eventsState = useAnalyticsEvents(range, { status: "error" });
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);

  const bucket: "hour" | "day" =
    range.end.getTime() - range.start.getTime() <= 2 * 24 * 60 * 60 * 1000 ? "hour" : "day";

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Errors</h1>
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      {seriesError && (
        <Alert variant="destructive">
          <AlertTriangleIcon />
          <AlertTitle>Failed to load chart data</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{seriesError}</span>
            <Button size="sm" variant="outline" onClick={() => void refetch()}>
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Errors over time</CardTitle>
        </CardHeader>
        <CardContent>
          <MetricChart
            data={timeseries ? timeseries.errors : null}
            bucket={bucket}
            isLoading={seriesLoading}
            valueFormatter={(n) => n.toLocaleString()}
          />
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-2 text-sm font-medium">Failed requests</h2>
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
      </div>

      <TraceSheet
        requestId={selectedRequestId}
        onOpenChange={(open) => !open && setSelectedRequestId(null)}
      />
    </div>
  );
}
