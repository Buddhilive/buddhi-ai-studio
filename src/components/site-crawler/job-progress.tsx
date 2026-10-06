"use client";

import * as React from "react";
import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  ClockIcon,
  Loader2Icon,
  StopCircleIcon,
  XCircleIcon,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { JobStatus, JobStatusType } from "@/lib/site-crawler/types";

function statusBadge(status: JobStatusType) {
  switch (status) {
    case "running":
      return (
        <Badge variant="outline" className="text-xs gap-1 border-blue-500/30 text-blue-600 dark:text-blue-400 bg-blue-500/10">
          <Loader2Icon className="h-3 w-3 animate-spin" />
          Running
        </Badge>
      );
    case "completed":
      return (
        <Badge variant="outline" className="text-xs gap-1 border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10">
          <CheckCircle2Icon className="h-3 w-3" />
          Completed
        </Badge>
      );
    case "cancelled":
      return (
        <Badge variant="outline" className="text-xs gap-1 border-amber-500/30 text-amber-600 dark:text-amber-400 bg-amber-500/10">
          <StopCircleIcon className="h-3 w-3" />
          Cancelled
        </Badge>
      );
    case "failed":
    case "interrupted":
      return (
        <Badge variant="outline" className="text-xs gap-1 border-destructive/30 text-destructive bg-destructive/10">
          <XCircleIcon className="h-3 w-3" />
          {status === "interrupted" ? "Interrupted" : "Failed"}
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="text-xs gap-1">
          {status}
        </Badge>
      );
  }
}

export function JobProgressCard({
  jobStatus,
  onCancel,
  isCancelling = false,
}: {
  jobStatus: JobStatus;
  onCancel: () => void;
  isCancelling?: boolean;
}) {
  const { total, crawled, extracted, failed, records } = jobStatus.counts;
  const processed = extracted + failed;
  const percent = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
  const isTerminal = ["completed", "cancelled", "failed", "interrupted"].includes(jobStatus.status);

  return (
    <Card className="border-border/80 bg-card shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CardTitle className="text-base">Extraction Run Progress</CardTitle>
              {statusBadge(jobStatus.status)}
            </div>
            <p className="text-xs text-muted-foreground font-mono">
              Project: <span className="text-foreground">{jobStatus.slug}</span> ({jobStatus.bucket})
            </p>
          </div>

          <div className="flex items-center gap-3">
            {jobStatus.elapsed_s !== undefined && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
                <ClockIcon className="h-3.5 w-3.5" />
                <span>{jobStatus.elapsed_s}s elapsed</span>
              </div>
            )}

            {!isTerminal && (
              <Button
                variant="destructive"
                size="xs"
                className="h-7 text-xs gap-1"
                onClick={onCancel}
                disabled={isCancelling}
              >
                <StopCircleIcon className="h-3.5 w-3.5" />
                {isCancelling ? "Cancelling..." : "Cancel Run"}
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Progress Bar */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>
              {processed} of {total} pages processed ({percent}%)
            </span>
            <span>{records} structured records extracted</span>
          </div>
          <Progress value={percent} className="h-2" />
        </div>

        {/* Current URL indicator */}
        {!isTerminal && jobStatus.current_url && (
          <div className="p-2.5 rounded bg-muted/40 border border-border/40 text-xs flex items-center gap-2 truncate">
            <Loader2Icon className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />
            <span className="text-muted-foreground">Processing:</span>
            <span className="font-mono truncate text-foreground">{jobStatus.current_url}</span>
          </div>
        )}

        {/* Counts Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-1 text-center text-xs">
          <div className="p-2 rounded border border-border/40 bg-muted/20">
            <div className="text-muted-foreground text-[11px]">Total</div>
            <div className="font-semibold text-sm">{total}</div>
          </div>
          <div className="p-2 rounded border border-border/40 bg-muted/20">
            <div className="text-muted-foreground text-[11px]">Crawled</div>
            <div className="font-semibold text-sm">{crawled}</div>
          </div>
          <div className="p-2 rounded border border-border/40 bg-muted/20">
            <div className="text-muted-foreground text-[11px]">Extracted</div>
            <div className="font-semibold text-sm text-emerald-600 dark:text-emerald-400">{extracted}</div>
          </div>
          <div className="p-2 rounded border border-border/40 bg-muted/20">
            <div className="text-muted-foreground text-[11px]">Records</div>
            <div className="font-semibold text-sm text-primary">{records}</div>
          </div>
          <div className="p-2 rounded border border-border/40 bg-muted/20">
            <div className="text-muted-foreground text-[11px]">Failed</div>
            <div className={`font-semibold text-sm ${failed > 0 ? "text-destructive" : ""}`}>{failed}</div>
          </div>
        </div>

        {/* Errors Alert if any */}
        {jobStatus.recent_errors && jobStatus.recent_errors.length > 0 && (
          <div className="space-y-1.5 p-3 rounded-lg border border-destructive/20 bg-destructive/5 text-xs text-destructive">
            <div className="flex items-center gap-1.5 font-medium">
              <AlertTriangleIcon className="h-3.5 w-3.5" />
              <span>Recent Issues Encountered:</span>
            </div>
            <ul className="list-disc pl-5 space-y-0.5 text-[11px] text-muted-foreground">
              {jobStatus.recent_errors.map((err, i) => (
                <li key={i} className="truncate">
                  <span className="font-mono text-foreground">{err.url}</span>: {err.error}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
