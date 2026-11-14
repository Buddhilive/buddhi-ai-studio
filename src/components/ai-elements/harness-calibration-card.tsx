"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2Icon, FlaskConicalIcon, ShieldAlertIcon, SparklesIcon } from "lucide-react";

interface HarnessCalibrationCardProps {
  event: string;
  data: Record<string, unknown>;
}

const EVENT_LABELS: Record<string, { label: string; tag: string; tone: string }> = {
  "harness.propose": {
    label: "Harness² Propose",
    tag: "[PROPOSE]",
    tone: "border-amber-600/40 bg-amber-500/10 text-amber-800 dark:text-amber-300",
  },
  "harness.probe": {
    label: "Harness² Sandbox Probe",
    tag: "[PROBE]",
    tone: "border-emerald-600/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
  },
  "harness.compose": {
    label: "Harness² Contrastive Compose",
    tag: "[COMPOSE]",
    tone: "border-sky-600/40 bg-sky-500/10 text-sky-800 dark:text-sky-300",
  },
  "harness.distill": {
    label: "Harness² Experience Distilled",
    tag: "[DISTILL]",
    tone: "border-primary/40 bg-primary/10 text-foreground",
  },
};

export function HarnessCalibrationCard({ event, data }: HarnessCalibrationCardProps) {
  const meta = EVENT_LABELS[event] ?? {
    label: "Harness² Calibration",
    tag: "[HARNESS]",
    tone: "border-border bg-muted text-foreground",
  };

  const isRunning = event === "harness.propose" || event === "harness.probe";
  const violations = Array.isArray(data.guardrail_violations)
    ? (data.guardrail_violations as string[])
    : [];

  return (
    <Card className="my-2 border border-border bg-card shadow-none" aria-busy={isRunning}>
      <CardHeader className="flex flex-row items-center justify-between gap-2 py-2.5 px-3.5">
        <CardTitle className="flex items-center gap-2 text-xs font-medium">
          {event === "harness.probe" ? (
            <FlaskConicalIcon className="size-3.5 text-emerald-700 dark:text-emerald-400" aria-hidden="true" />
          ) : event === "harness.compose" ? (
            <CheckCircle2Icon className="size-3.5 text-sky-700 dark:text-sky-400" aria-hidden="true" />
          ) : (
            <SparklesIcon className="size-3.5 text-amber-700 dark:text-amber-400" aria-hidden="true" />
          )}
          <span>{meta.label}</span>
        </CardTitle>
        <Badge variant="outline" className={`font-mono text-[11px] ${meta.tone}`}>
          {meta.tag}
        </Badge>
      </CardHeader>
      <CardContent className="px-3.5 pb-3 pt-0 text-xs text-muted-foreground space-y-1.5">
        {event === "harness.propose" && (
          <div className="flex flex-wrap items-center gap-3 font-mono tabular-nums">
            <span>round={String(data.round ?? 1)}</span>
            <span>candidates={String(data.candidate_count ?? 0)}</span>
            {Boolean(data.rlm_used) && (
              <Badge variant="secondary" className="text-[11px]">
                RLM Trace Slicing Active
              </Badge>
            )}
            {Number(data.rejected_static ?? 0) > 0 && (
              <span className="text-destructive">
                [GUARDRAIL BLOCKED: {String(data.rejected_static)}]
              </span>
            )}
          </div>
        )}

        {event === "harness.probe" && (
          <div className="flex flex-wrap items-center gap-3 font-mono tabular-nums">
            <span>candidate={String(data.candidate_id ?? "")}</span>
            <span>status=[{String(data.status ?? "").toUpperCase()}]</span>
            <span>steps={String(data.steps_taken ?? 0)}</span>
            <span>errors={String(data.tool_error_count ?? 0)}</span>
            <span>pass_rate={Number(data.test_pass_rate ?? 0).toFixed(2)}</span>
            <span>wall={String(data.wall_clock_ms ?? 0)}ms</span>
          </div>
        )}

        {event === "harness.compose" && (
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-3 font-mono tabular-nums">
              <span>outcome=[{String(data.status ?? "").toUpperCase()}]</span>
              {data.winning_candidate_id != null && (
                <span>winner={String(data.winning_candidate_id)}</span>
              )}
            </div>
            {Array.isArray(data.adopted_components) && data.adopted_components.length > 0 && (
              <p className="font-mono text-[11px] text-foreground">
                Adopted: {(data.adopted_components as string[]).join(", ")}
              </p>
            )}
          </div>
        )}

        {event === "harness.distill" && (
          <p className="max-w-[65ch] text-foreground">
            {String(data.lesson ?? "")}
          </p>
        )}

        {violations.length > 0 && (
          <div className="flex items-start gap-1.5 text-destructive">
            <ShieldAlertIcon className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <span>{violations.join("; ")}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
