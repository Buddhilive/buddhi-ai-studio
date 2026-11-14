import type { AgentEvent, AgentEventType } from "./agent-events";

export type TrajectoryCategory =
  | "thought"
  | "response"
  | "tool"
  | "shell"
  | "lifecycle"
  | "egm"
  | "harness"
  | "error";

export interface TokenUsageSummary {
  inputTokens: number | null;
  outputTokens: number | null;
  cachedTokens: number | null;
  totalTokens: number | null;
  durationMs: number | null;
}

export interface TrajectoryEventItem {
  id: string;
  seq: number;
  runId: string;
  turnId: string;
  spanId: string | null;
  parentSpanId: string | null;
  node: string | null;
  category: TrajectoryCategory;
  eventType: AgentEventType;
  title: string;
  summary: string;
  timestampMs: number;
  durationMs?: number;
  status: "running" | "completed" | "error" | "paused";
  toolCallId?: string;
  toolName?: string;
  argumentsText?: string;
  stdoutText?: string;
  stderrText?: string;
  exitCode?: number;
  truncated?: boolean;
  payloadText: string;
  rawEvents: AgentEvent[];
}

export interface TrajectorySpanNode {
  spanId: string;
  parentSpanId: string | null;
  label: string;
  status: "running" | "completed" | "error" | "paused";
  startedAtMs: number;
  endedAtMs?: number;
  durationMs?: number;
  items: TrajectoryEventItem[];
  children: TrajectorySpanNode[];
}

export interface TrajectoryTurnGroup {
  turnId: string;
  turnIndex: number;
  promptPreview: string;
  startedAtMs: number;
  endedAtMs?: number;
  durationMs?: number;
  status: "running" | "completed" | "error" | "paused";
  usage: TokenUsageSummary;
  items: TrajectoryEventItem[];
  spans: TrajectorySpanNode[];
}

export function categorizeEvent(event: AgentEvent): TrajectoryCategory {
  const t = event.event;
  if (t === "reasoning.delta") return "thought";
  if (t === "text.delta") return "response";
  if (t === "error") return "error";
  if (t.startsWith("egm.")) return "egm";
  if (t.startsWith("harness.")) return "harness";
  if (t === "tool.output.delta") return "shell";
  if (t === "tool.call" || t === "tool.args.delta" || t === "tool.result") {
    const toolName = String(event.data?.tool_name ?? "");
    if (toolName === "run_command" || toolName === "run_python_repl") {
      return "shell";
    }
    return "tool";
  }
  return "lifecycle";
}

function defaultTurnId(event: AgentEvent): string {
  return event.turn_id || "turn_0";
}

function eventTimestampMs(event: AgentEvent): number {
  if (typeof event.timestamp_ms === "number" && event.timestamp_ms > 0) {
    return event.timestamp_ms;
  }
  return Math.round((event.timestamp || Date.now() / 1000) * 1000);
}

export function buildTrajectoryTurns(events: AgentEvent[]): TrajectoryTurnGroup[] {
  // Deduplicate by seq (> 0) and sort chronologically
  const seenSeq = new Set<number>();
  const ordered: AgentEvent[] = [];
  for (const ev of events) {
    const seq = typeof ev.seq === "number" ? ev.seq : 0;
    if (seq > 0) {
      if (seenSeq.has(seq)) continue;
      seenSeq.add(seq);
    }
    ordered.push(ev);
  }
  ordered.sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0) || eventTimestampMs(a) - eventTimestampMs(b));

  const turnsMap = new Map<string, TrajectoryTurnGroup>();
  const turnsOrder: TrajectoryTurnGroup[] = [];
  const toolItemByCallId = new Map<string, TrajectoryEventItem>();
  let turnCounter = 0;

  const ensureTurn = (turnId: string, tsMs: number, promptPreview = ""): TrajectoryTurnGroup => {
    let group = turnsMap.get(turnId);
    if (!group) {
      turnCounter += 1;
      group = {
        turnId,
        turnIndex: turnCounter,
        promptPreview: promptPreview || `Turn ${turnCounter}`,
        startedAtMs: tsMs,
        status: "running",
        usage: {
          inputTokens: null,
          outputTokens: null,
          cachedTokens: null,
          totalTokens: null,
          durationMs: null,
        },
        items: [],
        spans: [],
      };
      turnsMap.set(turnId, group);
      turnsOrder.push(group);
    }
    return group;
  };

  for (let idx = 0; idx < ordered.length; idx++) {
    const ev = ordered[idx];
    const tsMs = eventTimestampMs(ev);
    const seq = ev.seq ?? idx + 1;
    const turnId = defaultTurnId(ev);
    const category = categorizeEvent(ev);

    if (ev.event === "turn.start") {
      const preview = String(ev.data?.prompt_preview ?? "").trim();
      const group = ensureTurn(turnId, tsMs, preview);
      if (preview) group.promptPreview = preview;
      group.startedAtMs = tsMs;
      continue;
    }

    const group = ensureTurn(turnId, tsMs);

    if (ev.event === "turn.end") {
      group.endedAtMs = tsMs;
      group.durationMs =
        typeof ev.data?.duration_ms === "number" ? ev.data.duration_ms : Math.max(0, tsMs - group.startedAtMs);
      const st = String(ev.data?.status ?? "completed");
      group.status = st === "error" || st === "failed" ? "error" : "completed";
      continue;
    }

    if (ev.event === "usage.update") {
      group.usage = {
        inputTokens: typeof ev.data?.input_tokens === "number" ? ev.data.input_tokens : group.usage.inputTokens,
        outputTokens: typeof ev.data?.output_tokens === "number" ? ev.data.output_tokens : group.usage.outputTokens,
        cachedTokens: typeof ev.data?.cached_tokens === "number" ? ev.data.cached_tokens : group.usage.cachedTokens,
        totalTokens: typeof ev.data?.total_tokens === "number" ? ev.data.total_tokens : group.usage.totalTokens,
        durationMs: typeof ev.data?.duration_ms === "number" ? ev.data.duration_ms : group.usage.durationMs,
      };
      continue;
    }

    // Coalesce consecutive reasoning.delta or text.delta in same turn + node + span
    if (ev.event === "reasoning.delta" || ev.event === "text.delta") {
      const delta = String(ev.data?.delta ?? "");
      const last = group.items[group.items.length - 1];
      if (
        last &&
        last.eventType === ev.event &&
        last.node === (ev.node ?? null) &&
        last.spanId === (ev.span_id ?? null)
      ) {
        last.payloadText += delta;
        last.summary = last.payloadText.slice(0, 140).replace(/\s+/g, " ").trim();
        last.rawEvents.push(ev);
        continue;
      }
      group.items.push({
        id: `${turnId}:${ev.event}:${seq}`,
        seq,
        runId: ev.run_id,
        turnId,
        spanId: ev.span_id ?? null,
        parentSpanId: ev.parent_span_id ?? null,
        node: ev.node ?? null,
        category,
        eventType: ev.event,
        title: ev.event === "reasoning.delta" ? "Thought" : "Response",
        summary: delta.slice(0, 140).replace(/\s+/g, " ").trim(),
        timestampMs: tsMs,
        status: "running",
        payloadText: delta,
        rawEvents: [ev],
      });
      continue;
    }

    // Pair tool.args.delta, tool.call, tool.output.delta, and tool.result by tool_call_id
    if (
      ev.event === "tool.args.delta" ||
      ev.event === "tool.call" ||
      ev.event === "tool.output.delta" ||
      ev.event === "tool.result"
    ) {
      const callId = String(ev.data?.tool_call_id ?? `call_${seq}`);
      const toolName = String(ev.data?.tool_name ?? "tool");
      let item = toolItemByCallId.get(callId);
      if (!item) {
        item = {
          id: `tool:${callId}`,
          seq,
          runId: ev.run_id,
          turnId,
          spanId: ev.span_id ?? null,
          parentSpanId: ev.parent_span_id ?? null,
          node: ev.node ?? null,
          category,
          eventType: ev.event,
          title: toolName,
          summary: `${toolName} (running)`,
          timestampMs: tsMs,
          status: "running",
          toolCallId: callId,
          toolName,
          argumentsText: "",
          stdoutText: "",
          stderrText: "",
          payloadText: "",
          rawEvents: [],
        };
        toolItemByCallId.set(callId, item);
        group.items.push(item);
      }
      item.rawEvents.push(ev);

      if (ev.event === "tool.args.delta") {
        item.argumentsText = `${item.argumentsText ?? ""}${String(ev.data?.delta ?? "")}`;
        item.summary = `${toolName} ${item.argumentsText.slice(0, 90)}`;
      } else if (ev.event === "tool.call") {
        const args = ev.data?.arguments;
        item.argumentsText = typeof args === "string" ? args : JSON.stringify(args ?? {}, null, 2);
        item.summary = `${toolName} (${item.argumentsText.slice(0, 90).replace(/\s+/g, " ")})`;
      } else if (ev.event === "tool.output.delta") {
        const stream = ev.data?.stream === "stderr" ? "stderr" : "stdout";
        const chunk = String(ev.data?.delta ?? "");
        if (stream === "stderr") {
          item.stderrText = `${item.stderrText ?? ""}${chunk}`;
        } else {
          item.stdoutText = `${item.stdoutText ?? ""}${chunk}`;
        }
        item.payloadText = `${item.stdoutText ?? ""}${item.stderrText ? `\n[stderr]\n${item.stderrText}` : ""}`;
        item.summary = `${toolName} streaming (${item.payloadText.length} chars)`;
      } else if (ev.event === "tool.result") {
        const resultStatus = String(ev.data?.status ?? "completed");
        const out = String(ev.data?.output ?? "");
        item.status = resultStatus === "error" || resultStatus === "timeout" ? "error" : "completed";
        item.exitCode = typeof ev.data?.exit_code === "number" ? ev.data.exit_code : 0;
        item.truncated = Boolean(ev.data?.truncated);
        item.durationMs = Math.max(0, tsMs - item.timestampMs);
        if (!item.stdoutText && out) {
          item.stdoutText = out;
        }
        item.payloadText = out || item.payloadText;
        item.summary = `${toolName} → ${item.status} (exit ${item.exitCode}, ${item.durationMs}ms)`;
      }
      continue;
    }

    // Lifecycle, EGM, Harness, Error
    const itemStatus =
      ev.event === "error"
        ? "error"
        : ev.event === "egm.gate.pause"
          ? "paused"
          : "completed";
    group.items.push({
      id: `${turnId}:${ev.event}:${seq}`,
      seq,
      runId: ev.run_id,
      turnId,
      spanId: ev.span_id ?? null,
      parentSpanId: ev.parent_span_id ?? null,
      node: ev.node ?? null,
      category,
      eventType: ev.event,
      title: ev.event,
      summary: JSON.stringify(ev.data ?? {}).slice(0, 140),
      timestampMs: tsMs,
      status: itemStatus,
      payloadText: JSON.stringify(ev.data ?? {}, null, 2),
      rawEvents: [ev],
    });

    if (ev.event === "run.end") {
      group.status = String(ev.data?.status ?? "") === "failed" ? "error" : "completed";
      group.endedAtMs = tsMs;
    }
  }

  // Finalize streaming thought/response items when turn ended and build span trees
  for (const turn of turnsOrder) {
    if (turn.status !== "running") {
      for (const item of turn.items) {
        if ((item.eventType === "reasoning.delta" || item.eventType === "text.delta") && item.status === "running") {
          item.status = "completed";
        }
      }
    }
    turn.spans = buildSpanTree(turn.items);
  }

  return turnsOrder;
}

export function buildSpanTree(items: TrajectoryEventItem[]): TrajectorySpanNode[] {
  const nodes = new Map<string, TrajectorySpanNode>();
  const roots: TrajectorySpanNode[] = [];

  for (const item of items) {
    if (!item.spanId) continue;
    let node = nodes.get(item.spanId);
    if (!node) {
      node = {
        spanId: item.spanId,
        parentSpanId: item.parentSpanId,
        label: item.node ? `${item.node} (${item.spanId})` : item.spanId,
        status: item.status,
        startedAtMs: item.timestampMs,
        items: [],
        children: [],
      };
      nodes.set(item.spanId, node);
    }
    node.items.push(item);
    node.endedAtMs = item.timestampMs;
    node.durationMs = Math.max(0, node.endedAtMs - node.startedAtMs);
    if (item.status === "error") node.status = "error";
    else if (node.status === "running" && item.status === "completed") node.status = "completed";
  }

  for (const node of nodes.values()) {
    if (node.parentSpanId && nodes.has(node.parentSpanId)) {
      nodes.get(node.parentSpanId)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

export function exportTrajectoryJson(runId: string, events: AgentEvent[]): void {
  const blob = new Blob([JSON.stringify({ run_id: runId, events }, null, 2)], {
    type: "application/json",
  });
  triggerDownload(blob, `trajectory-${runId}.json`);
}

export function exportTrajectoryJsonl(runId: string, events: AgentEvent[]): void {
  const lines = events.map((ev) => JSON.stringify(ev)).join("\n");
  const blob = new Blob([lines ? `${lines}\n` : ""], {
    type: "application/x-ndjson",
  });
  triggerDownload(blob, `trajectory-${runId}.jsonl`);
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
