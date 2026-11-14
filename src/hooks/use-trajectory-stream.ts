"use client";

import { useCallback, useMemo, useReducer } from "react";
import type { UIMessage } from "ai";
import type { AgentEvent } from "@/lib/agent-events";
import {
  buildTrajectoryTurns,
  type TrajectoryCategory,
  type TrajectoryEventItem,
  type TrajectoryTurnGroup,
} from "@/lib/trajectory-stream";

export interface TrajectoryUIState {
  selectedCategories: Set<TrajectoryCategory>;
  searchQuery: string;
  collapsedTurnIds: Set<string>;
  collapsedLaneKeys: Set<string>;
  autoScroll: boolean;
  scrollPausedByUser: boolean;
  inspectedEventId: string | null;
}

type TrajectoryAction =
  | { type: "toggle_category"; category: TrajectoryCategory }
  | { type: "clear_categories" }
  | { type: "set_search"; query: string }
  | { type: "toggle_turn"; turnId: string }
  | { type: "toggle_lane"; laneKey: string }
  | { type: "set_auto_scroll"; enabled: boolean }
  | { type: "set_scroll_paused"; paused: boolean }
  | { type: "inspect_event"; eventId: string | null };

function reducer(state: TrajectoryUIState, action: TrajectoryAction): TrajectoryUIState {
  switch (action.type) {
    case "toggle_category": {
      const next = new Set(state.selectedCategories);
      if (next.has(action.category)) next.delete(action.category);
      else next.add(action.category);
      return { ...state, selectedCategories: next };
    }
    case "clear_categories":
      return { ...state, selectedCategories: new Set() };
    case "set_search":
      return { ...state, searchQuery: action.query };
    case "toggle_turn": {
      const next = new Set(state.collapsedTurnIds);
      if (next.has(action.turnId)) next.delete(action.turnId);
      else next.add(action.turnId);
      return { ...state, collapsedTurnIds: next };
    }
    case "toggle_lane": {
      const next = new Set(state.collapsedLaneKeys);
      if (next.has(action.laneKey)) next.delete(action.laneKey);
      else next.add(action.laneKey);
      return { ...state, collapsedLaneKeys: next };
    }
    case "set_auto_scroll":
      return { ...state, autoScroll: action.enabled, scrollPausedByUser: action.enabled ? false : state.scrollPausedByUser };
    case "set_scroll_paused":
      return { ...state, scrollPausedByUser: action.paused };
    case "inspect_event":
      return { ...state, inspectedEventId: action.eventId };
  }
}

export function extractTrajectoryEventsFromMessages(messages: UIMessage[]): AgentEvent[] {
  const events: AgentEvent[] = [];
  for (const msg of messages) {
    if (!Array.isArray(msg.parts)) continue;
    for (const part of msg.parts) {
      const p = part as Record<string, unknown>;
      if (p.type === "data-trajectory" && p.data && typeof p.data === "object") {
        events.push(p.data as AgentEvent);
      }
    }
  }
  return events;
}

export function useTrajectoryStream(events: AgentEvent[], mode: "live" | "replay") {
  const [uiState, dispatch] = useReducer(reducer, {
    selectedCategories: new Set<TrajectoryCategory>(),
    searchQuery: "",
    collapsedTurnIds: new Set<string>(),
    collapsedLaneKeys: new Set<string>(),
    autoScroll: mode === "live",
    scrollPausedByUser: false,
    inspectedEventId: null,
  });

  const turns = useMemo(() => buildTrajectoryTurns(events), [events]);

  const filteredTurns: TrajectoryTurnGroup[] = useMemo(() => {
    const query = uiState.searchQuery.trim().toLowerCase();
    const hasFilter = uiState.selectedCategories.size > 0 || query.length > 0;
    if (!hasFilter) return turns;

    return turns
      .map((turn) => {
        const items = turn.items.filter((item) => {
          if (uiState.selectedCategories.size > 0 && !uiState.selectedCategories.has(item.category)) {
            return false;
          }
          if (query) {
            const haystack = `${item.title} ${item.summary} ${item.node ?? ""} ${item.payloadText}`.toLowerCase();
            if (!haystack.includes(query)) return false;
          }
          return true;
        });
        return { ...turn, items };
      })
      .filter((turn) => turn.items.length > 0);
  }, [turns, uiState.selectedCategories, uiState.searchQuery]);

  const allItems: TrajectoryEventItem[] = useMemo(
    () => turns.flatMap((t) => t.items),
    [turns]
  );

  const inspectedItem = useMemo(
    () => allItems.find((item) => item.id === uiState.inspectedEventId) ?? null,
    [allItems, uiState.inspectedEventId]
  );

  const runId = events[0]?.run_id ?? "";

  const toggleCategory = useCallback((category: TrajectoryCategory) => {
    dispatch({ type: "toggle_category", category });
  }, []);
  const clearCategories = useCallback(() => dispatch({ type: "clear_categories" }), []);
  const setSearch = useCallback((query: string) => dispatch({ type: "set_search", query }), []);
  const toggleTurn = useCallback((turnId: string) => dispatch({ type: "toggle_turn", turnId }), []);
  const toggleLane = useCallback((laneKey: string) => dispatch({ type: "toggle_lane", laneKey }), []);
  const setAutoScroll = useCallback((enabled: boolean) => dispatch({ type: "set_auto_scroll", enabled }), []);
  const setScrollPaused = useCallback((paused: boolean) => dispatch({ type: "set_scroll_paused", paused }), []);
  const inspectEvent = useCallback((eventId: string | null) => dispatch({ type: "inspect_event", eventId }), []);

  return {
    runId,
    turns: filteredTurns,
    totalEventsCount: events.length,
    totalItemsCount: allItems.length,
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
  };
}
