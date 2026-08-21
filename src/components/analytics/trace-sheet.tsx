"use client";

import type { ReactNode } from "react";
import { AlertTriangleIcon, InfoIcon } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatDateTime } from "@/lib/date-range";
import { useAnalyticsEventDetail } from "@/hooks/use-analytics-event-detail";
import { StatusBadge } from "@/components/analytics/status-badge";
import { JsonViewer } from "@/components/analytics/json-viewer";

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-muted-foreground text-xs">{label}</span>
      <span className="text-sm">{value}</span>
    </div>
  );
}

export function TraceSheet({
  requestId,
  onOpenChange,
}: {
  requestId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { event, isLoading, error } = useAnalyticsEventDetail(requestId);

  return (
    <Sheet open={requestId !== null} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle className="font-mono text-sm">{requestId}</SheetTitle>
          <SheetDescription>Trace detail</SheetDescription>
        </SheetHeader>

        <ScrollArea className="flex-1 px-4 pb-4">
          {isLoading && (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-48 w-full" />
            </div>
          )}

          {error && !isLoading && (
            <Alert variant="destructive">
              <AlertTriangleIcon />
              <AlertTitle>Failed to load trace</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {event && !isLoading && !error && (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Status" value={<StatusBadge status={event.status} />} />
                <Field label="Model" value={event.model_name} />
                <Field label="Time" value={formatDateTime(event.ts)} />
                <Field label="Latency" value={`${Math.round(event.latency_ms)}ms`} />
                <Field label="Prompt tokens" value={event.prompt_tokens} />
                <Field label="Completion tokens" value={event.completion_tokens} />
                <Field label="Total tokens" value={event.total_tokens} />
                <Field label="Streaming" value={event.stream ? "Yes" : "No"} />
              </div>

              {event.error_message && (
                <Alert variant="destructive">
                  <AlertTriangleIcon />
                  <AlertTitle>Request error</AlertTitle>
                  <AlertDescription>{event.error_message}</AlertDescription>
                </Alert>
              )}

              {(event.input_text === null && event.output_text === null) && (
                <Alert>
                  <InfoIcon />
                  <AlertTitle>Trace text unavailable</AlertTitle>
                  <AlertDescription>
                    Prompt/response text was not recorded for this request (trace logging is
                    disabled, or the text has aged out of the retention window).
                  </AlertDescription>
                </Alert>
              )}

              {event.input_text !== null && (
                <div className="flex flex-col gap-1">
                  <span className="text-muted-foreground text-xs">Prompt</span>
                  <pre className="bg-muted whitespace-pre-wrap rounded-md p-3 text-sm">
                    {event.input_text}
                  </pre>
                </div>
              )}

              {event.output_text !== null && (
                <div className="flex flex-col gap-1">
                  <span className="text-muted-foreground text-xs">Response</span>
                  <pre className="bg-muted whitespace-pre-wrap rounded-md p-3 text-sm">
                    {event.output_text}
                  </pre>
                </div>
              )}

              <JsonViewer data={event} title="Full event JSON" />
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
