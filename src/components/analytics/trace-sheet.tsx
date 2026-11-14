"use client";

import * as React from "react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatDateTime } from "@/lib/date-range";
import { useAnalyticsEventDetail } from "@/hooks/use-analytics-event-detail";
import { StatusBadge } from "@/components/analytics/status-badge";
import { JsonViewer } from "@/components/analytics/json-viewer";
import { TrajectoryPanel } from "@/components/trajectory/trajectory-panel";
import type { AgentEvent } from "@/lib/agent-events";

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
  const [fetchedEvents, setFetchedEvents] = React.useState<{ runId: string; events: AgentEvent[] } | null>(null);
  const [trajLoading, setTrajLoading] = React.useState(false);

  const resolvedRunId = React.useMemo(() => {
    const meta = (event as { metadata?: Record<string, unknown> } | null)?.metadata;
    if (meta && typeof meta.run_id === "string" && meta.run_id) return meta.run_id;
    return requestId || "";
  }, [event, requestId]);

  const inlineTrajectory = React.useMemo(() => {
    const meta = (event as { metadata?: Record<string, unknown> } | null)?.metadata;
    if (meta && Array.isArray(meta.trajectory)) {
      return meta.trajectory as AgentEvent[];
    }
    return null;
  }, [event]);

  const trajectoryEvents = React.useMemo(() => {
    if (inlineTrajectory) return inlineTrajectory;
    if (fetchedEvents && fetchedEvents.runId === resolvedRunId) return fetchedEvents.events;
    return [];
  }, [inlineTrajectory, fetchedEvents, resolvedRunId]);

  React.useEffect(() => {
    if (!requestId || !resolvedRunId || inlineTrajectory) {
      return;
    }
    let cancelled = false;
    fetch(`/api/agent/runs/${encodeURIComponent(resolvedRunId)}/trajectory`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data && Array.isArray(data.events)) {
          setFetchedEvents({ runId: resolvedRunId, events: data.events as AgentEvent[] });
        }
      })
      .catch(() => {
        // Non-agent completions may not have a trajectory
      })
      .finally(() => {
        if (!cancelled) setTrajLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [requestId, resolvedRunId, inlineTrajectory]);

  return (
    <Sheet open={requestId !== null} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 overflow-hidden sm:max-w-3xl lg:max-w-4xl">
        <SheetHeader>
          <SheetTitle className="font-mono text-sm">{requestId}</SheetTitle>
          <SheetDescription>Trace detail</SheetDescription>
        </SheetHeader>

        {isLoading && (
          <div className="flex flex-col gap-3 px-4 pb-4">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        )}

        {error && !isLoading && (
          <div className="px-4 pb-4">
            <Alert variant="destructive">
              <AlertTriangleIcon />
              <AlertTitle>Failed to load trace</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          </div>
        )}

        {event && !isLoading && !error && (
          <Tabs defaultValue="overview" className="flex min-h-0 flex-1 flex-col">
            <div className="border-b border-border px-4">
              <TabsList variant="line">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="trajectory">
                  Trajectory{trajectoryEvents.length > 0 ? ` (${trajectoryEvents.length})` : ""}
                </TabsTrigger>
                <TabsTrigger value="raw">Raw JSON</TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="overview" className="min-h-0 flex-1">
              <ScrollArea className="h-full px-4 py-4">
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
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="trajectory" className="min-h-0 flex-1">
              {trajLoading ? (
                <div className="space-y-2 p-4">
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-32 w-full" />
                </div>
              ) : (
                <TrajectoryPanel
                  events={trajectoryEvents}
                  mode="replay"
                  runIdOverride={resolvedRunId}
                />
              )}
            </TabsContent>

            <TabsContent value="raw" className="min-h-0 flex-1">
              <ScrollArea className="h-full px-4 py-4">
                <JsonViewer data={event} title="Full event JSON" />
              </ScrollArea>
            </TabsContent>
          </Tabs>
        )}
      </SheetContent>
    </Sheet>
  );
}
