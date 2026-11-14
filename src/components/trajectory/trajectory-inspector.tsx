"use client";

import * as React from "react";
import { XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { JsonViewer } from "@/components/analytics/json-viewer";
import { TerminalOutput } from "@/components/ai-elements/terminal";
import type { TrajectoryEventItem } from "@/lib/trajectory-stream";

interface TrajectoryInspectorProps {
  item: TrajectoryEventItem;
  onClose: () => void;
}

export function TrajectoryInspector({ item, onClose }: TrajectoryInspectorProps) {
  const closeRef = React.useRef<HTMLButtonElement>(null);

  React.useEffect(() => {
    closeRef.current?.focus();
  }, [item.id]);

  React.useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const parsedArgs = React.useMemo(() => {
    if (!item.argumentsText) return null;
    try {
      return JSON.parse(item.argumentsText);
    } catch {
      return item.argumentsText;
    }
  }, [item.argumentsText]);

  const commandStr = React.useMemo(() => {
    if (parsedArgs && typeof parsedArgs === "object" && "command" in parsedArgs) {
      return String((parsedArgs as Record<string, unknown>).command ?? "");
    }
    return undefined;
  }, [parsedArgs]);

  return (
    <aside
      aria-label="Trajectory event inspector"
      className="flex h-full flex-col border-l border-border bg-card"
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="min-w-0">
          <h3 className="truncate font-mono text-xs font-semibold text-foreground">
            {item.title}
          </h3>
          <p className="font-mono text-[11px] text-muted-foreground">
            seq #{item.seq} · {item.eventType}
            {item.durationMs !== undefined ? ` · ${item.durationMs}ms` : ""}
          </p>
        </div>
        <Button
          ref={closeRef}
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Close inspector"
          onClick={onClose}
        >
          <XIcon className="size-4" aria-hidden="true" />
        </Button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-3 text-xs">
        <dl className="grid grid-cols-2 gap-2 rounded-md border border-border bg-muted/40 p-2 font-mono text-[11px]">
          <div>
            <dt className="text-muted-foreground">Run ID</dt>
            <dd className="truncate text-foreground">{item.runId || "—"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Turn / Node</dt>
            <dd className="truncate text-foreground">
              {item.turnId} / {item.node ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Span ID</dt>
            <dd className="truncate text-foreground">{item.spanId ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Parent Span</dt>
            <dd className="truncate text-foreground">{item.parentSpanId ?? "—"}</dd>
          </div>
        </dl>

        {item.category === "shell" && (
          <TerminalOutput
            command={commandStr}
            stdout={item.stdoutText || item.payloadText}
            stderr={item.stderrText}
            exitCode={item.exitCode ?? 0}
          />
        )}

        {parsedArgs !== null && (
          <JsonViewer data={parsedArgs} title="Arguments" />
        )}

        {item.category !== "shell" && item.payloadText && (
          <div className="space-y-1">
            <div className="font-mono text-[11px] font-medium text-muted-foreground">
              Payload
            </div>
            <pre
              tabIndex={0}
              aria-label="Event payload text"
              className="max-h-64 overflow-auto rounded-md border border-border bg-muted/40 p-2.5 font-mono text-xs text-foreground whitespace-pre-wrap break-words"
            >
              {item.payloadText}
            </pre>
          </div>
        )}

        <JsonViewer data={item.rawEvents} title={`Raw Events (${item.rawEvents.length})`} />
      </div>
    </aside>
  );
}
