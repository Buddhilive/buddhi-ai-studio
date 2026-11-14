"use client";

import * as React from "react";
import { DownloadIcon, PauseIcon, PlayIcon, SearchIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { AgentEvent } from "@/lib/agent-events";
import {
  exportTrajectoryJson,
  exportTrajectoryJsonl,
  type TrajectoryCategory,
  type TrajectoryEventItem,
} from "@/lib/trajectory-stream";
import { useTrajectoryStream } from "@/hooks/use-trajectory-stream";
import { TrajectoryTurnGroupCard } from "./trajectory-turn-group";
import { TrajectoryInspector } from "./trajectory-inspector";

const FILTER_CHIPS: { key: TrajectoryCategory; label: string }[] = [
  { key: "thought", label: "Thoughts" },
  { key: "response", label: "Response" },
  { key: "tool", label: "Tools" },
  { key: "shell", label: "Shell" },
  { key: "egm", label: "EGM" },
  { key: "harness", label: "Harness²" },
  { key: "error", label: "Errors" },
];

interface TrajectoryPanelProps {
  events: AgentEvent[];
  mode?: "live" | "replay";
  isStreaming?: boolean;
  runIdOverride?: string;
  className?: string;
}

export function TrajectoryPanel({
  events,
  mode = "live",
  isStreaming = false,
  runIdOverride,
  className,
}: TrajectoryPanelProps) {
  const {
    runId,
    turns,
    totalEventsCount,
    inspectedItem,
    uiState,
    toggleCategory,
    clearCategories,
    setSearch,
    toggleTurn,
    toggleLane,
    setAutoScroll,
    setScrollPaused,
    inspectEvent,
  } = useTrajectoryStream(events, mode);

  const effectiveRunId = runIdOverride || runId || "run";
  const scrollContainerRef = React.useRef<HTMLDivElement>(null);
  const lastTriggerRef = React.useRef<HTMLButtonElement | null>(null);

  // Coarse live-region announcements only (never per-token)
  const [liveStatus, setLiveStatus] = React.useState("");
  const prevStreamingRef = React.useRef(isStreaming);
  React.useEffect(() => {
    if (isStreaming && !prevStreamingRef.current) {
      setLiveStatus("Trajectory stream started.");
    } else if (!isStreaming && prevStreamingRef.current) {
      setLiveStatus(`Trajectory stream completed (${totalEventsCount} events).`);
    }
    prevStreamingRef.current = isStreaming;
  }, [isStreaming, totalEventsCount]);

  React.useEffect(() => {
    if (mode !== "live" || !uiState.autoScroll || uiState.scrollPausedByUser) return;
    const el = scrollContainerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [events.length, mode, uiState.autoScroll, uiState.scrollPausedByUser]);

  const handleScroll = React.useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el || mode !== "live" || !uiState.autoScroll) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distanceFromBottom > 48 && !uiState.scrollPausedByUser) {
      setScrollPaused(true);
      setLiveStatus("Auto-scroll paused.");
    } else if (distanceFromBottom <= 16 && uiState.scrollPausedByUser) {
      setScrollPaused(false);
    }
  }, [mode, uiState.autoScroll, uiState.scrollPausedByUser, setScrollPaused]);

  const handleSelectEvent = React.useCallback(
    (item: TrajectoryEventItem, triggerEl: HTMLButtonElement | null) => {
      lastTriggerRef.current = triggerEl;
      inspectEvent(uiState.inspectedEventId === item.id ? null : item.id);
    },
    [inspectEvent, uiState.inspectedEventId]
  );

  const handleCloseInspector = React.useCallback(() => {
    inspectEvent(null);
    lastTriggerRef.current?.focus();
  }, [inspectEvent]);

  return (
    <div className={cn("flex h-full min-h-0 flex-col bg-background", className)}>
      <div role="status" aria-live="polite" className="sr-only">
        {liveStatus}
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-card px-3 py-2">
        <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Filter trajectory events">
          <button
            type="button"
            aria-pressed={uiState.selectedCategories.size === 0}
            onClick={clearCategories}
            className={cn(
              "rounded border px-2 py-0.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              uiState.selectedCategories.size === 0
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-muted text-muted-foreground hover:text-foreground"
            )}
          >
            All
          </button>
          {FILTER_CHIPS.map((chip) => {
            const active = uiState.selectedCategories.has(chip.key);
            return (
              <button
                key={chip.key}
                type="button"
                aria-pressed={active}
                onClick={() => toggleCategory(chip.key)}
                className={cn(
                  "rounded border px-2 py-0.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  active
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-muted text-muted-foreground hover:text-foreground"
                )}
              >
                {chip.label}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2">
          <div className="relative w-48">
            <SearchIcon
              className="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              type="search"
              value={uiState.searchQuery}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search trajectory..."
              aria-label="Search trajectory events"
              className="h-7 pl-7 text-xs"
            />
          </div>

          {mode === "live" && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setAutoScroll(!uiState.autoScroll || uiState.scrollPausedByUser);
              }}
              aria-pressed={uiState.autoScroll && !uiState.scrollPausedByUser}
              className="h-7 gap-1 text-xs"
            >
              {uiState.autoScroll && !uiState.scrollPausedByUser ? (
                <>
                  <PauseIcon className="size-3" aria-hidden="true" />
                  <span>Auto-scroll</span>
                </>
              ) : (
                <>
                  <PlayIcon className="size-3" aria-hidden="true" />
                  <span>Resume scroll</span>
                </>
              )}
            </Button>
          )}

          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={events.length === 0}
            onClick={() => exportTrajectoryJson(effectiveRunId, events)}
            className="h-7 gap-1 text-xs"
          >
            <DownloadIcon className="size-3" aria-hidden="true" />
            <span>JSON</span>
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={events.length === 0}
            onClick={() => exportTrajectoryJsonl(effectiveRunId, events)}
            className="h-7 gap-1 text-xs"
          >
            <DownloadIcon className="size-3" aria-hidden="true" />
            <span>JSONL</span>
          </Button>
        </div>
      </div>

      {/* Main Split Area */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          aria-busy={isStreaming}
          className="flex-1 space-y-2.5 overflow-y-auto p-3"
        >
          {turns.length === 0 ? (
            <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-border text-xs text-muted-foreground">
              {events.length === 0
                ? "No trajectory events recorded yet."
                : "No events match the active filter."}
            </div>
          ) : (
            turns.map((turn) => (
              <TrajectoryTurnGroupCard
                key={turn.turnId}
                turn={turn}
                isCollapsed={uiState.collapsedTurnIds.has(turn.turnId)}
                onToggleTurn={toggleTurn}
                collapsedLaneKeys={uiState.collapsedLaneKeys}
                onToggleLane={toggleLane}
                inspectedEventId={uiState.inspectedEventId}
                onSelectEvent={handleSelectEvent}
              />
            ))
          )}
        </div>

        {inspectedItem && (
          <div className="w-96 shrink-0">
            <TrajectoryInspector item={inspectedItem} onClose={handleCloseInspector} />
          </div>
        )}
      </div>
    </div>
  );
}
