"use client";

import * as React from "react";
import { TerminalIcon, CopyIcon, CheckIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export interface TerminalOutputProps {
  command?: string;
  stdout?: string;
  stderr?: string;
  exitCode?: number;
  className?: string;
}

export function TerminalOutput({
  command,
  stdout = "",
  stderr = "",
  exitCode = 0,
  className,
}: TerminalOutputProps) {
  const [copied, setCopied] = React.useState(false);

  const fullText = React.useMemo(() => {
    let text = "";
    if (command) text += `$ ${command}\n`;
    if (stdout) text += stdout;
    if (stderr) text += `\n[STDERR]\n${stderr}`;
    return text;
  }, [command, stdout, stderr]);

  const handleCopy = React.useCallback(async () => {
    if (!fullText) return;
    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  }, [fullText]);

  const isSuccess = exitCode === 0;

  return (
    <div
      className={cn(
        "my-2 rounded-lg border bg-zinc-950 text-zinc-100 font-mono text-xs overflow-hidden shadow-sm",
        className
      )}
    >
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900 border-b border-zinc-800">
        <div className="flex items-center gap-2 overflow-hidden">
          <TerminalIcon className="size-3.5 text-zinc-400 shrink-0" aria-hidden="true" />
          <span className="text-zinc-300 font-medium truncate">
            {command ? `$ ${command}` : "Sandbox Terminal"}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Badge
            variant="outline"
            className={cn(
              "text-[10px] px-1.5 py-0 border",
              isSuccess
                ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                : "text-rose-400 border-rose-500/30 bg-rose-500/10"
            )}
          >
            exit: {exitCode}
          </Badge>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleCopy}
            className="size-6 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
            aria-label="Copy terminal output"
          >
            {copied ? (
              <CheckIcon className="size-3 text-emerald-400" aria-hidden="true" />
            ) : (
              <CopyIcon className="size-3" aria-hidden="true" />
            )}
          </Button>
        </div>
      </div>
      <pre
        tabIndex={0}
        aria-label="Terminal output stream"
        className="p-3 overflow-x-auto max-h-64 whitespace-pre-wrap leading-relaxed text-[11px] focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-zinc-400"
      >
        {stdout && <span>{stdout}</span>}
        {stderr && (
          <span className="text-rose-400 block mt-1">{stderr}</span>
        )}
        {!stdout && !stderr && (
          <span className="text-zinc-500 italic">(No output produced)</span>
        )}
      </pre>
    </div>
  );
}
