"use client";

import * as React from "react";
import { AlertOctagonIcon, ChevronDownIcon, ChevronRightIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface StackFrame {
  file: string;
  line?: number;
  column?: number;
  fn?: string;
  raw?: string;
}

export interface StackTraceProps {
  errorType?: string;
  message: string;
  frames?: StackFrame[];
  rawTrace?: string;
  onOpenFile?: (file: string, line?: number) => void;
  className?: string;
}

export function parseStackTrace(raw: string): {
  errorType: string;
  message: string;
  frames: StackFrame[];
} {
  const lines = raw.split(/\r?\n/);
  const frames: StackFrame[] = [];
  const pyRe = /File "([^"]+)", line (\d+)(?:, in (.+))?/;
  const jsRe = /at\s+(?:([^\s(]+)\s+\()?([^():\s]+):(\d+):(\d+)\)?/;
  const tsRe = /^([^\s:(]+)\((\d+),(\d+)\):\s+error\s+(TS\d+):\s+(.*)$/;

  let errorType = "RuntimeError";
  let message = lines[lines.length - 1]?.trim() || "Execution failed";

  for (const line of lines) {
    const pyMatch = line.match(pyRe);
    if (pyMatch) {
      frames.push({
        file: pyMatch[1].replace(/^\/workspace\//, ""),
        line: Number(pyMatch[2]),
        fn: pyMatch[3],
        raw: line.trim(),
      });
      continue;
    }
    const jsMatch = line.match(jsRe);
    if (jsMatch) {
      frames.push({
        file: jsMatch[2].replace(/^\/workspace\//, ""),
        line: Number(jsMatch[3]),
        column: Number(jsMatch[4]),
        fn: jsMatch[1],
        raw: line.trim(),
      });
      continue;
    }
    const tsMatch = line.match(tsRe);
    if (tsMatch) {
      errorType = tsMatch[4];
      message = tsMatch[5];
      frames.push({
        file: tsMatch[1].replace(/^\/workspace\//, ""),
        line: Number(tsMatch[2]),
        column: Number(tsMatch[3]),
        raw: line.trim(),
      });
    }
  }

  return { errorType, message, frames };
}

export function StackTrace({
  errorType = "Error",
  message,
  frames = [],
  rawTrace,
  onOpenFile,
  className,
}: StackTraceProps) {
  const [expanded, setExpanded] = React.useState(true);

  return (
    <div
      role="region"
      aria-label="Stack trace"
      className={cn(
        "overflow-hidden rounded-lg border border-destructive/40 bg-card text-xs",
        className
      )}
    >
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between gap-2 border-b border-destructive/20 bg-destructive/10 px-3 py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="flex min-w-0 items-center gap-2">
          <AlertOctagonIcon className="size-4 shrink-0 text-destructive" aria-hidden="true" />
          <Badge variant="destructive" className="font-mono text-[10px]">
            {errorType}
          </Badge>
          <span className="truncate font-medium text-foreground">{message}</span>
        </div>
        {expanded ? (
          <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        ) : (
          <ChevronRightIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        )}
      </button>

      {expanded && (
        <div className="divide-y divide-border/50 p-2 font-mono text-[11px]">
          {frames.length > 0 ? (
            frames.map((frame, idx) => (
              <div key={`${frame.file}-${frame.line}-${idx}`} className="flex items-center justify-between gap-2 px-2 py-1">
                <div className="min-w-0 truncate text-muted-foreground">
                  {frame.fn && <span className="mr-1.5 text-foreground">{frame.fn}</span>}
                  {onOpenFile ? (
                    <button
                      type="button"
                      onClick={() => onOpenFile(frame.file, frame.line)}
                      className="underline decoration-primary/60 underline-offset-2 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {frame.file}
                      {frame.line ? `:${frame.line}` : ""}
                    </button>
                  ) : (
                    <span>
                      {frame.file}
                      {frame.line ? `:${frame.line}` : ""}
                    </span>
                  )}
                </div>
              </div>
            ))
          ) : (
            <pre className="overflow-x-auto whitespace-pre-wrap p-2 text-muted-foreground">
              {rawTrace || message}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
