"use client";

import * as React from "react";
import { TerminalIcon, CheckCircle2Icon, AlertCircleIcon, ClockIcon, CopyIcon, CheckIcon, Trash2Icon } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export interface ExecutionResultData {
  status: "completed" | "timeout" | "error";
  stdout: string;
  stderr: string;
  exit_code: number;
  execution_time_ms: number;
}

interface TerminalOutputProps {
  result: ExecutionResultData | null;
  onClear: () => void;
  isLoading: boolean;
}

export function TerminalOutput({ result, onClear, isLoading }: TerminalOutputProps) {
  const [copied, setCopied] = React.useState(false);

  const fullOutput = React.useMemo(() => {
    if (!result) return "";
    let out = "";
    if (result.stdout) out += result.stdout;
    if (result.stderr) {
      if (out && !out.endsWith("\n")) out += "\n";
      out += `[STDERR]\n${result.stderr}`;
    }
    return out;
  }, [result]);

  const handleCopy = async () => {
    if (!fullOutput) return;
    await navigator.clipboard.writeText(fullOutput);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card className="flex flex-col h-full border border-border/80 shadow-sm bg-card overflow-hidden">
      <CardHeader className="py-3 px-4 border-b border-border/60 flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <TerminalIcon className="w-4 h-4 text-primary" />
          <CardTitle className="text-base font-semibold">Console Output</CardTitle>
          {result && (
            <div className="flex items-center gap-1.5 ml-2">
              <Badge
                variant={
                  result.status === "completed"
                    ? "default"
                    : result.status === "timeout"
                    ? "secondary"
                    : "destructive"
                }
                className="text-[11px] h-5 px-1.5 capitalize flex items-center gap-1"
              >
                {result.status === "completed" ? (
                  <CheckCircle2Icon className="w-3 h-3 text-emerald-400" />
                ) : (
                  <AlertCircleIcon className="w-3 h-3" />
                )}
                {result.status}
              </Badge>

              <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-mono">
                exit: {result.exit_code}
              </Badge>

              <span className="text-[11px] text-muted-foreground flex items-center gap-1 ml-1">
                <ClockIcon className="w-3 h-3" />
                {Math.round(result.execution_time_ms)}ms
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1">
          {result && (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={handleCopy}
                title="Copy output"
              >
                {copied ? <CheckIcon className="w-3.5 h-3.5 text-emerald-500" /> : <CopyIcon className="w-3.5 h-3.5" />}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                onClick={onClear}
                title="Clear console"
              >
                <Trash2Icon className="w-3.5 h-3.5" />
              </Button>
            </>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex-1 p-0 relative font-mono text-xs bg-black/90 text-zinc-100 min-h-[300px] overflow-auto">
        {isLoading ? (
          <div className="p-4 text-zinc-400 animate-pulse flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-primary animate-ping" />
            <span>Executing inside container sandbox...</span>
          </div>
        ) : !result ? (
          <div className="p-6 text-zinc-500 text-center flex flex-col items-center justify-center h-full gap-2">
            <TerminalIcon className="w-8 h-8 opacity-40" />
            <p>No execution output yet.</p>
            <p className="text-[11px] text-zinc-600">Click &ldquo;Run&rdquo; to execute code and view output here.</p>
          </div>
        ) : (
          <div className="p-4 whitespace-pre-wrap break-words leading-relaxed select-text font-mono">
            {result.stdout && <span>{result.stdout}</span>}
            {result.stderr && (
              <span className="text-red-400 block mt-2">
                {result.stdout ? "\n" : ""}
                {result.stderr}
              </span>
            )}
            {!result.stdout && !result.stderr && (
              <span className="text-zinc-500 italic">[Process finished with exit code {result.exit_code} and no output]</span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
