"use client";

import { AlertTriangleIcon, ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime } from "@/lib/date-range";
import type { EventsPage, LlmEventSummary } from "@/hooks/use-analytics-events";
import { StatusBadge } from "@/components/analytics/status-badge";

export function EventsTable({
  page,
  isLoading,
  error,
  onRowClick,
  onRetry,
  hasNext,
  hasPrev,
  onNext,
  onPrev,
}: {
  page: EventsPage | null;
  isLoading: boolean;
  error: string | null;
  onRowClick: (event: LlmEventSummary) => void;
  onRetry: () => void;
  hasNext: boolean;
  hasPrev: boolean;
  onNext: () => void;
  onPrev: () => void;
}) {
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangleIcon />
        <AlertTitle>Failed to load traces</AlertTitle>
        <AlertDescription className="flex items-center justify-between gap-4">
          <span>{error}</span>
          <Button size="sm" variant="outline" onClick={onRetry}>
            Try again
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Prompt</TableHead>
              <TableHead className="text-right">Completion</TableHead>
              <TableHead className="text-right">Latency</TableHead>
              <TableHead>Stream</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading &&
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 7 }).map((__, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}

            {!isLoading && page?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-muted-foreground h-24 text-center">
                  No matching traces
                </TableCell>
              </TableRow>
            )}

            {!isLoading &&
              page?.items.map((event) => (
                <TableRow
                  key={event.request_id}
                  className="cursor-pointer"
                  onClick={() => onRowClick(event)}
                >
                  <TableCell>{formatDateTime(event.ts)}</TableCell>
                  <TableCell className="font-mono text-xs">{event.model_name}</TableCell>
                  <TableCell>
                    <StatusBadge status={event.status} />
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{event.prompt_tokens}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {event.completion_tokens}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {Math.round(event.latency_ms)}ms
                  </TableCell>
                  <TableCell>{event.stream ? "Yes" : "No"}</TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </div>

      {page && page.total > 0 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {page.offset + 1}-{Math.min(page.offset + page.items.length, page.total)} of{" "}
            {page.total}
          </span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={!hasPrev} onClick={onPrev}>
              <ChevronLeftIcon className="size-4" />
              Prev
            </Button>
            <Button size="sm" variant="outline" disabled={!hasNext} onClick={onNext}>
              Next
              <ChevronRightIcon className="size-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
