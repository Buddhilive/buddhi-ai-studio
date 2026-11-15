"use client";

import * as React from "react";
import Ansi from "ansi-to-react";
import { TerminalIcon, CopyIcon, CheckIcon, Trash2Icon, PlayIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface TerminalOutputProps {
  command?: string;
  stdout?: string;
  stderr?: string;
  exitCode?: number;
  onClear?: () => void;
  onExecute?: (command: string) => Promise<void> | void;
  isRunning?: boolean;
  className?: string;
}

export function TerminalOutput({
  command,
  stdout = "",
  stderr = "",
  exitCode = 0,
  onClear,
  onExecute,
  isRunning = false,
  className,
}: TerminalOutputProps) {
  const [copied, setCopied] = React.useState(false);
  const [inputCmd, setInputCmd] = React.useState("");

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

  const handleRunSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputCmd.trim();
    if (!trimmed || !onExecute || isRunning) return;
    setInputCmd("");
    await onExecute(trimmed);
  };

  const isSuccess = exitCode === 0;

  return (
    <div
      className={cn(
        "my-2 flex flex-col rounded-lg border bg-zinc-950 text-zinc-100 font-mono text-xs overflow-hidden shadow-sm",
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
          {onClear && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={onClear}
              className="size-6 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
              aria-label="Clear terminal output"
            >
              <Trash2Icon className="size-3" aria-hidden="true" />
            </Button>
          )}
          <Button
            type="button"
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
        className="flex-1 p-3 overflow-x-auto max-h-64 whitespace-pre-wrap leading-relaxed text-[11px] focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-zinc-400"
      >
        {stdout && (
          <span>
            <Ansi>{stdout}</Ansi>
          </span>
        )}
        {stderr && (
          <span className="text-rose-400 block mt-1">
            <Ansi>{stderr}</Ansi>
          </span>
        )}
        {!stdout && !stderr && (
          <span className="text-zinc-500 italic">(No output produced)</span>
        )}
      </pre>
      {onExecute && (
        <form
          onSubmit={(e) => void handleRunSubmit(e)}
          className="flex items-center gap-2 border-t border-zinc-800 bg-zinc-900/70 px-3 py-1.5"
        >
          <span className="text-emerald-400 select-none">$</span>
          <Input
            aria-label="Run command in OpenSandbox"
            placeholder="Type command and press Enter..."
            value={inputCmd}
            onChange={(e) => setInputCmd(e.target.value)}
            disabled={isRunning}
            className="h-7 border-0 bg-transparent px-1 font-mono text-xs text-zinc-100 placeholder:text-zinc-500 focus-visible:ring-0"
          />
          <Button
            type="submit"
            size="sm"
            variant="ghost"
            disabled={isRunning || !inputCmd.trim()}
            className="h-6 gap-1 px-2 text-[11px] text-zinc-300 hover:bg-zinc-800 hover:text-white"
          >
            <PlayIcon className="size-3" aria-hidden="true" />
            <span>Run</span>
          </Button>
        </form>
      )}
    </div>
  );
}
