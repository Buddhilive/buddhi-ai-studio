"use client";

import * as React from "react";
import { CheckCircle2Icon, SkipForwardIcon, XCircleIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface TestCaseResult {
  name: string;
  status: "passed" | "failed" | "skipped";
  durationMs?: number;
  error?: string;
}

export interface TestResultsProps {
  suite?: string;
  passed: number;
  failed: number;
  skipped?: number;
  durationMs?: number;
  cases?: TestCaseResult[];
  className?: string;
}

export function TestResults({
  suite = "Test Suite",
  passed,
  failed,
  skipped = 0,
  durationMs,
  cases = [],
  className,
}: TestResultsProps) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card text-xs",
        className
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/40 px-3 py-2">
        <span className="font-semibold">{suite}</span>
        <div className="flex items-center gap-2 font-mono text-[11px] tabular-nums">
          <Badge
            variant="outline"
            className="gap-1 border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
          >
            <CheckCircle2Icon className="size-3" aria-hidden="true" />
            <span>{passed} passed</span>
          </Badge>
          {failed > 0 && (
            <Badge variant="destructive" className="gap-1">
              <XCircleIcon className="size-3" aria-hidden="true" />
              <span>{failed} failed</span>
            </Badge>
          )}
          {skipped > 0 && (
            <Badge variant="secondary" className="gap-1">
              <SkipForwardIcon className="size-3" aria-hidden="true" />
              <span>{skipped} skipped</span>
            </Badge>
          )}
          {typeof durationMs === "number" && (
            <span className="text-muted-foreground">{durationMs}ms</span>
          )}
        </div>
      </div>

      {cases.length > 0 && (
        <ul className="divide-y divide-border/60">
          {cases.map((tc, idx) => (
            <li key={`${tc.name}-${idx}`} className="px-3 py-2">
              <div className="flex items-center justify-between gap-2 font-mono text-[11px]">
                <span className="flex items-center gap-1.5">
                  {tc.status === "passed" && (
                    <CheckCircle2Icon className="size-3.5 text-emerald-500" aria-hidden="true" />
                  )}
                  {tc.status === "failed" && (
                    <XCircleIcon className="size-3.5 text-destructive" aria-hidden="true" />
                  )}
                  {tc.status === "skipped" && (
                    <SkipForwardIcon className="size-3.5 text-muted-foreground" aria-hidden="true" />
                  )}
                  <span>{tc.name}</span>
                </span>
                <span className="text-muted-foreground">
                  {tc.status.toUpperCase()}
                  {typeof tc.durationMs === "number" ? ` (${tc.durationMs}ms)` : ""}
                </span>
              </div>
              {tc.error && (
                <pre className="mt-1.5 overflow-x-auto rounded bg-destructive/10 p-2 font-mono text-[11px] text-destructive">
                  {tc.error}
                </pre>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
