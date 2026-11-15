"use client";

import * as React from "react";
import { BotIcon, CheckCircle2Icon, Loader2Icon, ShieldAlertIcon, SparklesIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type AgentRole = "elephant" | "goldfish" | "rlm" | "calibrator" | "assistant";

export interface AgentProps {
  name?: string;
  role?: AgentRole;
  model?: string;
  status?: "idle" | "running" | "completed" | "error";
  stepLabel?: string;
  tokenCount?: number;
  className?: string;
}

const ROLE_STYLES: Record<AgentRole, { label: string; badgeClass: string }> = {
  elephant: {
    label: "Elephant Architect",
    badgeClass:
      "border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300",
  },
  goldfish: {
    label: "Goldfish Reviewer",
    badgeClass:
      "border-sky-500/40 bg-sky-500/10 text-sky-800 dark:text-sky-300",
  },
  rlm: {
    label: "RLM Explorer",
    badgeClass:
      "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
  },
  calibrator: {
    label: "Harness Calibrator",
    badgeClass:
      "border-primary/40 bg-primary/10 text-primary",
  },
  assistant: {
    label: "Coding Agent",
    badgeClass: "border-border bg-secondary text-secondary-foreground",
  },
};

export function Agent({
  name,
  role = "assistant",
  model,
  status = "running",
  stepLabel,
  tokenCount,
  className,
}: AgentProps) {
  const meta = ROLE_STYLES[role] ?? ROLE_STYLES.assistant;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs",
        className
      )}
    >
      <div className="flex items-center gap-2">
        {role === "calibrator" ? (
          <SparklesIcon className="size-4 text-primary" aria-hidden="true" />
        ) : (
          <BotIcon className="size-4 text-muted-foreground" aria-hidden="true" />
        )}
        <span className="font-medium text-foreground">{name || meta.label}</span>
        <Badge variant="outline" className={cn("text-[10px]", meta.badgeClass)}>
          {meta.label}
        </Badge>
        {model && (
          <Badge variant="secondary" className="font-mono text-[10px]">
            {model}
          </Badge>
        )}
      </div>

      <div className="flex items-center gap-2 font-mono text-[11px] tabular-nums text-muted-foreground">
        {typeof tokenCount === "number" && <span>{tokenCount.toLocaleString()} tok</span>}
        {stepLabel && <span>{stepLabel}</span>}
        <span
          aria-live="polite"
          className="inline-flex items-center gap-1 font-sans font-medium text-foreground"
        >
          {status === "running" && (
            <>
              <Loader2Icon className="size-3 animate-spin text-primary" aria-hidden="true" />
              <span>Running</span>
            </>
          )}
          {status === "completed" && (
            <>
              <CheckCircle2Icon className="size-3 text-emerald-500" aria-hidden="true" />
              <span>Completed</span>
            </>
          )}
          {status === "error" && (
            <>
              <ShieldAlertIcon className="size-3 text-destructive" aria-hidden="true" />
              <span>Error</span>
            </>
          )}
          {status === "idle" && <span>Idle</span>}
        </span>
      </div>
    </div>
  );
}
