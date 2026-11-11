"use client";

import * as React from "react";
import { CheckCircle2Icon, CircleIcon, Loader2Icon, XCircleIcon, ListTodoIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PlanStep } from "@/lib/agent-events";

export interface PlanProps {
  steps: PlanStep[];
  className?: string;
}

export function Plan({ steps, className }: PlanProps) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className={cn("my-2 rounded-lg border bg-card p-3 shadow-xs text-xs", className)}>
      <div className="flex items-center gap-2 mb-2 font-semibold text-foreground border-b pb-1.5">
        <ListTodoIcon className="size-4 text-primary" aria-hidden="true" />
        <span>Execution Plan ({steps.filter((s) => s.status === "completed").length}/{steps.length})</span>
      </div>
      <ol className="space-y-1.5 list-none pl-0 m-0">
        {steps.map((step, idx) => {
          let icon = <CircleIcon className="size-3.5 text-muted-foreground shrink-0 mt-0.5" aria-hidden="true" />;
          let label = "Pending";

          if (step.status === "completed") {
            icon = <CheckCircle2Icon className="size-3.5 text-emerald-500 shrink-0 mt-0.5" aria-hidden="true" />;
            label = "Completed";
          } else if (step.status === "in_progress") {
            icon = <Loader2Icon className="size-3.5 text-amber-500 animate-spin shrink-0 mt-0.5" aria-hidden="true" />;
            label = "In progress";
          } else if (step.status === "failed") {
            icon = <XCircleIcon className="size-3.5 text-rose-500 shrink-0 mt-0.5" aria-hidden="true" />;
            label = "Failed";
          }

          return (
            <li key={step.id || idx} className="flex items-start gap-2 text-muted-foreground">
              {icon}
              <div className="flex-1 overflow-hidden">
                <span
                  className={cn(
                    "text-foreground leading-snug",
                    step.status === "completed" && "line-through text-muted-foreground"
                  )}
                >
                  {step.title}
                </span>
                <span className="sr-only"> - {label}</span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
