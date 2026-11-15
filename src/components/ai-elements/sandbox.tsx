"use client";

import * as React from "react";
import { BoxIcon, RefreshCwIcon, ShieldCheckIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface SandboxProps {
  sessionId?: string | null;
  runtimeImage?: string;
  status?: "running" | "connecting" | "disconnected" | "completed" | "error";
  executionTimeMs?: number;
  stdout?: string;
  onRestart?: () => void;
  className?: string;
}

export function Sandbox({
  sessionId,
  runtimeImage = "buddhilive/vibe-sandbox:latest",
  status = "running",
  executionTimeMs,
  stdout,
  onRestart,
  className,
}: SandboxProps) {
  const isHealthy = status === "running" || status === "completed";

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card text-xs",
        className
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/40 px-3 py-2">
        <div className="flex items-center gap-2">
          <BoxIcon className="size-3.5 text-emerald-500" aria-hidden="true" />
          <span className="font-semibold">OpenSandbox</span>
          {sessionId && (
            <Badge variant="outline" className="font-mono text-[10px] tabular-nums">
              {sessionId.slice(0, 12)}
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-2">
          {typeof executionTimeMs === "number" && (
            <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
              {executionTimeMs}ms
            </span>
          )}
          <Badge
            variant="outline"
            className={cn(
              "gap-1 text-[10px]",
              isHealthy
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                : "border-destructive/40 bg-destructive/10 text-destructive"
            )}
          >
            <ShieldCheckIcon className="size-3" aria-hidden="true" />
            <span>{status}</span>
          </Badge>
          {status === "disconnected" && onRestart && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onRestart}
              className="h-6 gap-1 px-2 text-[11px]"
            >
              <RefreshCwIcon className="size-3" aria-hidden="true" />
              <span>Restart Sandbox</span>
            </Button>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between px-3 py-1.5 font-mono text-[11px] text-muted-foreground">
        <span>Image: {runtimeImage}</span>
      </div>

      {stdout && (
        <pre className="max-h-48 overflow-auto border-t border-border/60 bg-zinc-950 p-3 font-mono text-[11px] text-zinc-100">
          {stdout}
        </pre>
      )}
    </div>
  );
}
