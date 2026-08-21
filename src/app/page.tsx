"use client";

import { useState } from "react";
import {
  ActivityIcon,
  AlertTriangleIcon,
  CoinsIcon,
  TimerIcon,
  TriangleAlertIcon,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DateRangePicker } from "@/components/analytics/date-range-picker";
import { KpiCard } from "@/components/analytics/kpi-card";
import { MetricChart } from "@/components/analytics/metric-chart";
import { useAnalyticsSummary } from "@/hooks/use-analytics-summary";
import { presetToRange, type DateRange } from "@/lib/date-range";

export default function Dashboard() {
  const [range, setRange] = useState<DateRange>(() => presetToRange("7d"));
  const { summary, timeseries, isLoading, error, refetch } = useAnalyticsSummary(range);

  const hasData = !isLoading && !error && summary && summary.total_requests > 0;
  const isEmpty = !isLoading && !error && summary && summary.total_requests === 0;

  const bucket: "hour" | "day" =
    range.end.getTime() - range.start.getTime() <= 2 * 24 * 60 * 60 * 1000 ? "hour" : "day";

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground text-sm">
            Usage metrics and traces for chat completions.
          </p>
        </div>
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangleIcon />
          <AlertTitle>Failed to load analytics</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button size="sm" variant="outline" onClick={() => void refetch()}>
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {isEmpty && (
        <Alert>
          <AlertTriangleIcon />
          <AlertTitle>No requests recorded yet</AlertTitle>
          <AlertDescription>
            Send a chat completion request to start seeing metrics here.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-12">
        <div className="lg:col-span-3">
          <KpiCard
            title="Requests"
            value={summary ? summary.total_requests.toLocaleString() : "-"}
            isLoading={isLoading}
            icon={<ActivityIcon className="text-muted-foreground size-4" />}
          />
        </div>
        <div className="lg:col-span-3">
          <KpiCard
            title="Tokens"
            value={summary ? summary.total_tokens.toLocaleString() : "-"}
            isLoading={isLoading}
            icon={<CoinsIcon className="text-muted-foreground size-4" />}
          />
        </div>
        <div className="lg:col-span-3">
          <KpiCard
            title="Avg latency"
            value={summary ? `${Math.round(summary.avg_latency_ms)}ms` : "-"}
            isLoading={isLoading}
            icon={<TimerIcon className="text-muted-foreground size-4" />}
          />
        </div>
        <div className="lg:col-span-3">
          <KpiCard
            title="Error rate"
            value={summary ? `${(summary.error_rate * 100).toFixed(1)}%` : "-"}
            href="/analytics/errors"
            isLoading={isLoading}
            icon={<TriangleAlertIcon className="text-muted-foreground size-4" />}
          />
        </div>

        <Card className="sm:col-span-2 lg:col-span-6">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Requests over time</CardTitle>
          </CardHeader>
          <CardContent>
            <MetricChart
              data={timeseries ? timeseries.requests : null}
              bucket={bucket}
              isLoading={isLoading}
              valueFormatter={(n) => n.toLocaleString()}
            />
          </CardContent>
        </Card>
        <Card className="sm:col-span-2 lg:col-span-6">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Tokens over time</CardTitle>
          </CardHeader>
          <CardContent>
            <MetricChart
              data={timeseries ? timeseries.tokens : null}
              bucket={bucket}
              isLoading={isLoading}
              valueFormatter={(n) => n.toLocaleString()}
            />
          </CardContent>
        </Card>
        <Card className="sm:col-span-2 lg:col-span-12">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Latency over time</CardTitle>
          </CardHeader>
          <CardContent>
            <MetricChart
              data={timeseries ? timeseries.latency : null}
              bucket={bucket}
              isLoading={isLoading}
              valueFormatter={(n) => `${Math.round(n)}ms`}
            />
          </CardContent>
        </Card>
      </div>

      {hasData && summary.dropped_events > 0 && (
        <Alert>
          <AlertTriangleIcon />
          <AlertTitle>Some metrics events were dropped</AlertTitle>
          <AlertDescription>
            {summary.dropped_events} event(s) were dropped due to a full metrics queue. Counts
            above may be slightly incomplete.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
