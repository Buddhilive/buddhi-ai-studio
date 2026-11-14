"use client";

import * as React from "react";
import { ChevronDownIcon, ChevronRightIcon } from "lucide-react";
import type { TrajectoryCategory, TrajectoryEventItem } from "@/lib/trajectory-stream";
import { TrajectoryEventRow } from "./trajectory-event-row";

const LANE_LABELS: Record<TrajectoryCategory, string> = {
  thought: "Thought",
  response: "Response",
  tool: "Tools",
  shell: "Shell",
  egm: "EGM",
  harness: "Harness²",
  lifecycle: "Lifecycle",
  error: "Errors",
};

interface TrajectoryLaneProps {
  turnId: string;
  category: TrajectoryCategory;
  items: TrajectoryEventItem[];
  isCollapsed: boolean;
  onToggle: (laneKey: string) => void;
  inspectedEventId: string | null;
  onSelectEvent: (item: TrajectoryEventItem, triggerEl: HTMLButtonElement | null) => void;
}

export function TrajectoryLane({
  turnId,
  category,
  items,
  isCollapsed,
  onToggle,
  inspectedEventId,
  onSelectEvent,
}: TrajectoryLaneProps) {
  const laneKey = `${turnId}:${category}`;
  const panelId = `lane-panel-${turnId}-${category}`.replace(/[^a-zA-Z0-9_-]/g, "_");

  return (
    <div className="rounded-md border border-border bg-muted/30">
      <button
        type="button"
        aria-expanded={!isCollapsed}
        aria-controls={panelId}
        onClick={() => onToggle(laneKey)}
        className="flex w-full items-center justify-between px-2.5 py-1.5 text-left text-xs font-medium text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="flex items-center gap-1.5">
          {isCollapsed ? (
            <ChevronRightIcon className="size-3.5" aria-hidden="true" />
          ) : (
            <ChevronDownIcon className="size-3.5" aria-hidden="true" />
          )}
          <span>{LANE_LABELS[category]}</span>
        </span>
        <span className="font-mono tabular-nums text-[11px]">{items.length}</span>
      </button>

      {!isCollapsed && (
        <div id={panelId} className="space-y-1 border-t border-border p-1.5">
          {items.map((item) => (
            <TrajectoryEventRow
              key={item.id}
              item={item}
              isSelected={inspectedEventId === item.id}
              onSelect={onSelectEvent}
            />
          ))}
        </div>
      )}
    </div>
  );
}
