"use client";

import { Badge } from "@/components/ui/badge";
import { CheckCircle2Icon, Loader2Icon, XCircleIcon } from "lucide-react";

interface EgmPhaseBadgeProps {
  phase: string;
  round?: number;
  maxRounds?: number;
  reviewerStatuses?: Record<string, string>;
  specPath?: string;
}

export function EgmPhaseBadge({
  phase,
  round = 1,
  maxRounds = 3,
  reviewerStatuses = {},
  specPath,
}: EgmPhaseBadgeProps) {
  const isElephant = ["draft", "resolve", "analyze", "plan"].includes(phase);
  const isGoldfish = ["goldfish_review", "review", "goldfish_verify", "brainstorm"].includes(phase);

  return (
    <div
      role="region"
      aria-label="Elephant-Goldfish Workflow Telemetry"
      className="my-2 rounded-lg border border-border bg-card p-3 text-xs space-y-2"
    >
      {/* Role and Phase bar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {isElephant && (
            <Badge className="bg-amber-600/15 text-amber-700 dark:text-amber-300 border-amber-500/40 font-medium">
              Elephant • Architect
            </Badge>
          )}
          {isGoldfish && (
            <Badge className="bg-sky-600/15 text-sky-800 dark:text-sky-300 border-sky-500/40 font-medium">
              Goldfish • Auditor
            </Badge>
          )}
          <span className="font-semibold uppercase tracking-wider text-muted-foreground text-[10px]">
            Phase: <strong className="text-foreground">{phase}</strong>
          </span>
        </div>

        <div className="font-mono text-[11px] text-muted-foreground tabular-nums">
          Round {round}/{maxRounds}
        </div>
      </div>

      {/* Reviewer Pipeline Status Pills */}
      {Object.keys(reviewerStatuses).length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {Object.entries(reviewerStatuses).map(([lens, st]) => {
            const isCompleted = st === "completed";
            const isNotRun = st === "not run";
            const isRunning = st === "running" || st === "retrying";

            return (
              <span
                key={lens}
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono border ${
                  isCompleted
                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300"
                    : isNotRun
                    ? "border-destructive/40 bg-destructive/10 text-destructive"
                    : "border-sky-500/40 bg-sky-500/10 text-sky-800 dark:text-sky-300"
                }`}
              >
                {isCompleted && <CheckCircle2Icon className="size-3 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />}
                {isNotRun && <XCircleIcon className="size-3 text-destructive" aria-hidden="true" />}
                {isRunning && <Loader2Icon className="size-3 animate-spin text-sky-600" aria-hidden="true" />}
                <span>{lens}</span>
                <span className="sr-only">({st})</span>
              </span>
            );
          })}
        </div>
      )}

      {/* Spec path anchor */}
      {specPath && (
        <div className="text-[11px] text-muted-foreground font-mono truncate">
          Artifact: <span className="text-foreground font-semibold">{specPath}</span>
        </div>
      )}

      {/* Accessible live region for screen readers */}
      <div aria-live="polite" className="sr-only">
        Current EGM workflow phase is {phase}, round {round} of {maxRounds}.
      </div>
    </div>
  );
}
