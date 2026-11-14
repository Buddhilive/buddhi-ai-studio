"use client";

import * as React from "react";
import {
  AlertCircleIcon,
  BrainIcon,
  CpuIcon,
  MessageSquareTextIcon,
  ShieldCheckIcon,
  TerminalIcon,
  WrenchIcon,
  ActivityIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { TrajectoryCategory, TrajectoryEventItem } from "@/lib/trajectory-stream";

const CATEGORY_META: Record<
  TrajectoryCategory,
  { tag: string; badgeClass: string; Icon: React.ComponentType<{ className?: string }> }
> = {
  thought: {
    tag: "[THOUGHT]",
    badgeClass: "text-amber-700 dark:text-amber-300 border-amber-500/30 bg-amber-500/10",
    Icon: BrainIcon,
  },
  response: {
    tag: "[RESPONSE]",
    badgeClass: "text-foreground border-border bg-muted/60",
    Icon: MessageSquareTextIcon,
  },
  tool: {
    tag: "[TOOL]",
    badgeClass: "text-foreground border-border bg-secondary",
    Icon: WrenchIcon,
  },
  shell: {
    tag: "[SHELL]",
    badgeClass: "text-emerald-700 dark:text-emerald-300 border-emerald-500/30 bg-emerald-500/10",
    Icon: TerminalIcon,
  },
  egm: {
    tag: "[EGM]",
    badgeClass: "text-sky-800 dark:text-sky-300 border-sky-500/30 bg-sky-500/10",
    Icon: ShieldCheckIcon,
  },
  harness: {
    tag: "[HARNESS]",
    badgeClass: "text-accent-foreground border-border bg-accent/50",
    Icon: CpuIcon,
  },
  lifecycle: {
    tag: "[SYSTEM]",
    badgeClass: "text-muted-foreground border-border bg-muted/40",
    Icon: ActivityIcon,
  },
  error: {
    tag: "[ERROR]",
    badgeClass: "text-destructive border-destructive/40 bg-destructive/10",
    Icon: AlertCircleIcon,
  },
};

function formatTime(ms: number): string {
  const d = new Date(ms);
  return d.toISOString().slice(11, 23);
}

interface TrajectoryEventRowProps {
  item: TrajectoryEventItem;
  isSelected: boolean;
  onSelect: (item: TrajectoryEventItem, triggerEl: HTMLButtonElement | null) => void;
}

export function TrajectoryEventRow({ item, isSelected, onSelect }: TrajectoryEventRowProps) {
  const meta = CATEGORY_META[item.category];
  const Icon = meta.Icon;
  const btnRef = React.useRef<HTMLButtonElement>(null);

  return (
    <button
      ref={btnRef}
      type="button"
      onClick={() => onSelect(item, btnRef.current)}
      aria-pressed={isSelected}
      className={cn(
        "group flex w-full items-center gap-2 rounded-md border px-2.5 py-1.5 text-left font-mono text-[13px] transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isSelected
          ? "border-primary bg-accent/60 text-foreground"
          : "border-border bg-card hover:bg-muted/70 text-card-foreground"
      )}
    >
      <span
        className={cn(
          "inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium",
          meta.badgeClass
        )}
      >
        <Icon className="size-3" aria-hidden="true" />
        <span>{meta.tag}</span>
      </span>

      <span className="min-w-0 flex-1 truncate text-foreground">
        {item.summary || item.title}
      </span>

      {item.durationMs !== undefined && (
        <span className="shrink-0 tabular-nums text-[11px] text-muted-foreground">
          {item.durationMs}ms
        </span>
      )}

      <span
        className={cn(
          "shrink-0 rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide",
          item.status === "error"
            ? "bg-destructive/15 text-destructive"
            : item.status === "running"
              ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
              : "bg-muted text-muted-foreground"
        )}
      >
        {item.status}
      </span>

      <time
        dateTime={new Date(item.timestampMs).toISOString()}
        className="shrink-0 tabular-nums text-[11px] text-muted-foreground"
      >
        {formatTime(item.timestampMs)}
      </time>
    </button>
  );
}
