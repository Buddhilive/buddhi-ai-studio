"use client";

import * as React from "react";
import { BoxIcon, ShieldCheckIcon, AlertTriangleIcon } from "lucide-react";
import { CodeEditor } from "@/components/sandbox/code-editor";
import { TerminalOutput, ExecutionResultData } from "@/components/sandbox/terminal-output";
import { SessionManager, SandboxSessionItem } from "@/components/sandbox/session-manager";
import { Badge } from "@/components/ui/badge";

export default function SandboxPage() {
  const [code, setCode] = React.useState<string>(`# OpenSandbox Python Demo
import sys
import math

print(f"Running on Python {sys.version.split()[0]} in container")
print("Math calculations:")
for i in range(1, 6):
    print(f"  {i}^2 = {i**2}, sqrt({i}) = {math.sqrt(i):.4f}")
`);
  const [language, setLanguage] = React.useState<"python" | "bash" | "sh">("python");
  const [timeoutS, setTimeoutS] = React.useState<number>(60);
  const [allowNetwork, setAllowNetwork] = React.useState<boolean>(false);
  const [isExecuting, setIsExecuting] = React.useState<boolean>(false);
  const [executionResult, setExecutionResult] = React.useState<ExecutionResultData | null>(null);

  // Sessions state
  const [sessions, setSessions] = React.useState<SandboxSessionItem[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = React.useState<boolean>(false);
  const [healthStatus, setHealthStatus] = React.useState<{ connected: boolean; active: number } | null>(null);

  const fetchHealth = React.useCallback(async () => {
    try {
      const res = await fetch("/api/sandbox/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(Array.isArray(data) ? data : []);
        setHealthStatus({ connected: true, active: Array.isArray(data) ? data.length : 0 });
      } else {
        setHealthStatus({ connected: false, active: 0 });
      }
    } catch {
      setHealthStatus({ connected: false, active: 0 });
    }
  }, []);

  const fetchSessions = React.useCallback(async () => {
    setIsLoadingSessions(true);
    try {
      const res = await fetch("/api/sandbox/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error("Failed to fetch sessions:", err);
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  React.useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  const handleRun = async () => {
    if (!code.trim() || isExecuting) return;
    setIsExecuting(true);
    try {
      const res = await fetch("/api/sandbox/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          language,
          timeout_s: timeoutS,
          allow_network: allowNetwork,
        }),
      });

      if (res.ok) {
        const data: ExecutionResultData = await res.json();
        setExecutionResult(data);
      } else {
        const err = await res.json();
        setExecutionResult({
          status: "error",
          stdout: "",
          stderr: err.detail || err.error || "Failed to execute in sandbox",
          exit_code: 1,
          execution_time_ms: 0,
        });
      }
    } catch (err: unknown) {
      setExecutionResult({
        status: "error",
        stdout: "",
        stderr: String(err),
        exit_code: 1,
        execution_time_ms: 0,
      });
    } finally {
      setIsExecuting(false);
      fetchSessions();
    }
  };

  const handleCreateSession = async (runtimeImage: string) => {
    try {
      const res = await fetch("/api/sandbox/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ runtime_image: runtimeImage, timeout_s: 1800 }),
      });
      if (res.ok) {
        await fetchSessions();
      }
    } catch (err) {
      console.error("Failed to create session:", err);
    }
  };

  const handleTerminateSession = async (sessionId: string) => {
    try {
      const res = await fetch(`/api/sandbox/sessions/${sessionId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        await fetchSessions();
      }
    } catch (err) {
      console.error("Failed to terminate session:", err);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/60 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">OpenSandbox</h1>
            <Badge variant="outline" className="text-xs font-mono py-0 h-5">
              Service
            </Badge>
          </div>
          <p className="text-muted-foreground text-sm mt-0.5">
            Isolated code & command execution for AI agents and developer workflows.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {healthStatus && (
            <Badge
              variant={healthStatus.connected ? "outline" : "destructive"}
              className="text-xs px-2.5 py-1 gap-1.5"
            >
              {healthStatus.connected ? (
                <>
                  <ShieldCheckIcon className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Sandbox Engine Ready</span>
                </>
              ) : (
                <>
                  <AlertTriangleIcon className="w-3.5 h-3.5" />
                  <span>Daemon Standby</span>
                </>
              )}
            </Badge>
          )}
        </div>
      </div>

      {/* Main Execution Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch min-h-[440px]">
        <CodeEditor
          code={code}
          onChangeCode={setCode}
          language={language}
          onChangeLanguage={setLanguage}
          timeoutS={timeoutS}
          onChangeTimeout={setTimeoutS}
          allowNetwork={allowNetwork}
          onToggleNetwork={setAllowNetwork}
          onRun={handleRun}
          isLoading={isExecuting}
        />

        <TerminalOutput
          result={executionResult}
          onClear={() => setExecutionResult(null)}
          isLoading={isExecuting}
        />
      </div>

      {/* Stateful Sessions Section */}
      <SessionManager
        sessions={sessions}
        isLoading={isLoadingSessions}
        onRefresh={fetchSessions}
        onCreateSession={handleCreateSession}
        onTerminateSession={handleTerminateSession}
      />
    </div>
  );
}
