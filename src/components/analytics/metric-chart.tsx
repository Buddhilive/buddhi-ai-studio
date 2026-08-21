"use client";

import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Skeleton } from "@/components/ui/skeleton";
import { formatBucketLabel } from "@/lib/date-range";
import type { TimeseriesPoint } from "@/hooks/use-analytics-summary";

const chartConfig: ChartConfig = {
  value: {
    label: "Value",
    color: "var(--primary)",
  },
};

export function MetricChart({
  data,
  bucket,
  isLoading,
  valueFormatter,
}: {
  data: TimeseriesPoint[] | null;
  bucket: "hour" | "day";
  isLoading: boolean;
  valueFormatter?: (value: number) => string;
}) {
  if (isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (!data || data.length === 0) {
    return (
      <div className="text-muted-foreground flex h-64 w-full items-center justify-center rounded-md border border-dashed text-sm">
        No data for this range
      </div>
    );
  }

  const chartData = data.map((point) => ({
    label: formatBucketLabel(point.bucket, bucket),
    value: point.value,
  }));

  return (
    <ChartContainer config={chartConfig} className="h-64 w-full">
      <AreaChart data={chartData} margin={{ left: 12, right: 12 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} minTickGap={24} />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          width={48}
          tickFormatter={valueFormatter}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelKey="label"
              formatter={(value) =>
                valueFormatter ? valueFormatter(Number(value)) : String(value)
              }
            />
          }
        />
        <Area dataKey="value" type="monotone" fill="var(--color-value)" fillOpacity={0.2} stroke="var(--color-value)" />
      </AreaChart>
    </ChartContainer>
  );
}
