"use client";

import * as React from "react";
import { PlayIcon, RotateCcwIcon, GlobeIcon, ClockIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";

interface CodeEditorProps {
  code: string;
  onChangeCode: (code: string) => void;
  language: "python" | "bash" | "sh";
  onChangeLanguage: (lang: "python" | "bash" | "sh") => void;
  timeoutS: number;
  onChangeTimeout: (timeout: number) => void;
  allowNetwork: boolean;
  onToggleNetwork: (allowed: boolean) => void;
  onRun: () => void;
  isLoading: boolean;
}

const DEFAULT_TEMPLATES: Record<string, string> = {
  python: `# OpenSandbox Python Demo
import sys
import math

print(f"Running on Python {sys.version.split()[0]}")
numbers = [2, 4, 6, 8, 10]
roots = [math.sqrt(n) for n in numbers]
print(f"Computed roots: {roots}")
`,
  bash: `#!/usr/bin/env bash
echo "Hello from OpenSandbox container!"
uname -a
pwd
ls -la /
`,
  sh: `echo "Shell runtime active"
date
`,
};

export function CodeEditor({
  code,
  onChangeCode,
  language,
  onChangeLanguage,
  timeoutS,
  onChangeTimeout,
  allowNetwork,
  onToggleNetwork,
  onRun,
  isLoading,
}: CodeEditorProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      if (!isLoading) {
        onRun();
      }
    }
  };

  const handleLanguageChange = (val: string | null) => {
    if (!val) return;
    const lang = val as "python" | "bash" | "sh";
    onChangeLanguage(lang);
    if (!code || code === DEFAULT_TEMPLATES[language]) {
      onChangeCode(DEFAULT_TEMPLATES[lang] || "");
    }
  };

  const handleResetTemplate = () => {
    onChangeCode(DEFAULT_TEMPLATES[language] || "");
  };

  return (
    <Card className="flex flex-col h-full border border-border/80 shadow-sm bg-card">
      <CardHeader className="py-3 px-4 border-b border-border/60 flex flex-row items-center justify-between">
        <div className="space-y-0.5">
          <CardTitle className="text-base font-semibold">Sandbox Playground</CardTitle>
          <CardDescription className="text-xs text-muted-foreground">
            Execute code in an isolated container via OpenSandbox.
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <Select value={language} onValueChange={handleLanguageChange}>
            <SelectTrigger className="w-[120px] h-8 text-xs">
              <SelectValue placeholder="Runtime" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="python">Python 3</SelectItem>
              <SelectItem value="bash">Bash</SelectItem>
              <SelectItem value="sh">POSIX Shell</SelectItem>
            </SelectContent>
          </Select>

          <Button
            variant="outline"
            size="sm"
            className="h-8 px-2.5 text-xs text-muted-foreground"
            onClick={handleResetTemplate}
            title="Reset to default template"
          >
            <RotateCcwIcon className="w-3.5 h-3.5" />
          </Button>

          <Button
            size="sm"
            className="h-8 gap-1.5 text-xs font-medium"
            onClick={onRun}
            disabled={isLoading || !code.trim()}
          >
            {isLoading ? (
              <>
                <Spinner className="w-3.5 h-3.5" />
                <span>Running...</span>
              </>
            ) : (
              <>
                <PlayIcon className="w-3.5 h-3.5 fill-current" />
                <span>Run</span>
              </>
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex-1 p-0 flex flex-col min-h-[300px]">
        <textarea
          value={code}
          onChange={(e) => onChangeCode(e.target.value)}
          onKeyDown={handleKeyDown}
          spellCheck={false}
          className="flex-1 w-full p-4 font-mono text-xs bg-muted/20 text-foreground resize-none focus:outline-none focus:ring-0 border-0 leading-relaxed"
          placeholder="Type or paste code here... (Ctrl+Enter to run)"
        />

        <div className="px-4 py-2 border-t border-border/40 bg-muted/10 flex flex-wrap items-center justify-between text-xs text-muted-foreground gap-2">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5" title="Execution timeout in seconds">
              <ClockIcon className="w-3.5 h-3.5" />
              <span>Timeout:</span>
              <select
                value={timeoutS}
                onChange={(e) => onChangeTimeout(Number(e.target.value))}
                className="bg-transparent text-foreground border border-border/60 rounded px-1 py-0.5 text-xs"
              >
                <option value={10}>10s</option>
                <option value={30}>30s</option>
                <option value={60}>60s</option>
                <option value={120}>120s</option>
              </select>
            </div>

            <label className="flex items-center gap-1.5 cursor-pointer">
              <GlobeIcon className="w-3.5 h-3.5" />
              <span>Network:</span>
              <input
                type="checkbox"
                checked={allowNetwork}
                onChange={(e) => onToggleNetwork(e.target.checked)}
                className="rounded border-border text-primary focus:ring-0"
              />
              <span className={allowNetwork ? "text-emerald-500 font-medium" : "text-muted-foreground"}>
                {allowNetwork ? "Enabled" : "Disabled"}
              </span>
            </label>
          </div>

          <div className="text-[11px] text-muted-foreground/80">
            Press <kbd className="px-1 py-0.5 rounded bg-muted border border-border text-[10px]">Ctrl</kbd> + <kbd className="px-1 py-0.5 rounded bg-muted border border-border text-[10px]">Enter</kbd> to run
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
