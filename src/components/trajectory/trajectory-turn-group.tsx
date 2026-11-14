"use client";

import * as React from "react";
import { ChevronDownIcon, ChevronRightIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  TrajectoryCategory,
  TrajectoryEventItem,
  TrajectorySpanNode,
  TrajectoryTurnGroup,
} from "@/lib/trajectory-stream";
import { TrajectoryLane } from "./trajectory-lane";
import { TrajectoryEventRow } from "./trajectory-event-row";

const LANE_ORDER: TrajectoryCategory[] = [
  "thought",
  "tool",
  "shell",
  "egm",
  "harness",
  "response",
  "error",
  "lifecycle",
];

interface TrajectoryTurnGroupProps {
  turn: TrajectoryTurnGroup;
  isCollapsed: boolean;
  onToggleTurn: (turnId: string) => void;
  collapsedLaneKeys: Set<string>;
  onToggleLane: (laneKey: string) => void;
  inspectedEventId: string | null;
  onSelectEvent: (item: TrajectoryEventItem, triggerEl: HTMLButtonElement | null) => void;
}

function SpanBranch({
  span,
  depth = 0,
  inspectedEventId,
  onSelectEvent,
}: {
  span: TrajectorySpanNode;
  depth?: number;
  inspectedEventId: string | null;
  onSelectEvent: (item: TrajectoryEventItem, triggerEl: HTMLButtonElement | null) => void;
}) {
  const [open, setOpen] = React.useState(true);
  const panelId = `span-${span.spanId}`.replace(/[^a-zA-Z0-9_-]/g, "_");

  return (
    <div
      className={cn("rounded border border-border bg-card/70", depth > 0 && "ml-3")}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-2.5 py-1 text-left font-mono text-xs text-foreground hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="flex items-center gap-1.5 truncate">
          {open ? (
            <ChevronDownIcon className="size-3.5 shrink-0" aria-hidden="true" />
          ) : (
            <ChevronRightIcon className="size-3.5 shrink-0" aria-hidden="true" />
          )}
          <span className="truncate">{span.label}</span>
        </span>
        <span className="flex items-center gap-2 shrink-0 text-[11px] text-muted-foreground tabular-nums">
          <span>{span.status}</span>
          {span.durationMs !== undefined && <span>{span.durationMs}ms</span>}
        </span>
      </button>
      {open && (
        <div id={panelId} className="space-y-1 border-t border-border p-1.5">
          {span.items.map((item) => (
            <TrajectoryEventRow
              key={item.id}
              item={item}
              isSelected={inspectedEventId === item.id}
              onSelect={onSelectEvent}
            />
          ))}
          {span.children.map((child) => (
            <SpanBranch
              key={child.spanId}
              span={child}
              depth={depth + 1}
              inspectedEventId={inspectedEventId}
              onSelectEvent={onSelectEvent}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function TrajectoryTurnGroupCard({
  turn,
  isCollapsed,
  onToggleTurn,
  collapsedLaneKeys,
  onToggleLane,
  inspectedEventId,
  onSelectEvent,
}: TrajectoryTurnGroupProps) {
  const panelId = `turn-panel-${turn.turnId}`.replace(/[^a-zA-Z0-9_-]/g, "_");
  const grouped = React.useMemo(() => {
    const map = new Map<TrajectoryCategory, TrajectoryEventItem[]>();
    for (const item of turn.items) {
      const list = map.get(item.category) ?? [];
      list.push(item);
      map.set(item.category, list);
    }
    return map;
  }, [turn.items]);

  const tokenSummary =
    turn.usage.totalTokens !== null
      ? `${turn.usage.inputTokens ?? 0} in / ${turn.usage.outputTokens ?? 0} out (${turn.usage.totalTokens} tok)`
      : turn.usage.outputTokens !== null
        ? `${turn.usage.outputTokens} out tok`
        : "N/A tok";

  return (
    <section
      aria-label={`Turn ${turn.turnIndex}`}
      className="rounded-lg border border-border bg-card"
    >
      <button
        type="button"
        aria-expanded={!isCollapsed}
        aria-controls={panelId}
        onClick={() => onToggleTurn(turn.turnId)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="flex min-w-0 items-center gap-2">
          {isCollapsed ? (
            <ChevronRightIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          ) : (
            <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          )}
          <span className="shrink-0 font-mono text-xs font-semibold text-foreground">
            Turn {turn.turnIndex}
          </span>
          <span className="truncate text-xs text-muted-foreground">
            {turn.promptPreview}
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-2 font-mono text-[11px] tabular-nums text-muted-foreground">
          <span>{tokenSummary}</span>
          {turn.durationMs !== undefined && <span>{turn.durationMs}ms</span>}
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[10px] uppercase",
              turn.status === "error"
                ? "bg-destructive/15 text-destructive"
                : turn.status === "running"
                  ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
                  : "bg-muted text-muted-foreground"
            )}
          >
            {turn.status}
          </span>
        </div>
      </button>

      {!isCollapsed && (
        <div id={panelId} className="space-y-2 border-t border-border p-2.5">
          {turn.spans.length > 0 && (
            <div className="space-y-1">
              {turn.spans.map((span) => (
                <SpanBranch
                  key={span.spanId}
                  span={span}
                  inspectedEventId={inspectedEventId}
                  onSelectEvent={onSelectEvent}
                />
              ))}
            </div>
          )}

          {LANE_ORDER.map((cat) => {
            const laneItems = grouped.get(cat);
            if (!laneItems || laneItems.length === 0) return null;
            return (
              <TrajectoryLane
                key={cat}
                turnId={turn.turnId}
                category={cat}
                items={laneItems}
                isCollapsed={collapsedLaneKeys.has(`${turn.turnId}:${cat}`)}
                onToggle={onToggleLane}
                inspectedEventId={inspectedEventId}
                onSelectEvent={onSelectEvent}
              />
            );
          })}
        </div>
      )}
    </section>
  );
}
