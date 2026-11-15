"use client";

import * as React from "react";
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TerminalOutput } from "@/components/ai-elements/terminal";
import { TestResults, type TestCaseResult } from "@/components/ai-elements/test-results";
import { StackTrace, type StackFrame } from "@/components/ai-elements/stack-trace";
import { Commit, type CommitFileChange } from "@/components/ai-elements/commit";
import type { IdeBottomDockTab } from "@/components/build/project-workspace-context";

interface IdeBottomDockProps {
  activeTab: IdeBottomDockTab;
  onTabChange: (tab: IdeBottomDockTab) => void;
  terminalStdout: string;
  terminalStderr: string;
  terminalExitCode: number;
  terminalCommand: string;
  isExecuting: boolean;
  onExecuteCommand: (cmd: string) => Promise<void>;
  onClearTerminal: () => void;
  testSummary?: {
    suite: string;
    passed: number;
    failed: number;
    skipped?: number;
    cases?: TestCaseResult[];
  } | null;
  stackTrace?: {
    errorType: string;
    message: string;
    frames: StackFrame[];
    rawTrace?: string;
  } | null;
  onOpenFile: (path: string, line?: number) => void;
  commits?: Array<{
    hash: string;
    message: string;
    branch?: string;
    files?: CommitFileChange[];
  }>;
}

export function IdeBottomDock({
  activeTab,
  onTabChange,
  terminalStdout,
  terminalStderr,
  terminalExitCode,
  terminalCommand,
  isExecuting,
  onExecuteCommand,
  onClearTerminal,
  testSummary,
  stackTrace,
  onOpenFile,
  commits = [],
}: IdeBottomDockProps) {
  const [collapsed, setCollapsed] = React.useState(false);

  return (
    <div className="flex flex-col border-t border-border bg-card">
      <Tabs
        value={activeTab}
        onValueChange={(v) => {
          onTabChange(v as IdeBottomDockTab);
          if (collapsed) setCollapsed(false);
        }}
        className="flex flex-col gap-0"
      >
        <div className="flex items-center justify-between border-b border-border px-2 py-1">
          <TabsList variant="line" className="h-7">
            <TabsTrigger value="terminal" className="px-2.5 text-xs">
              Terminal
            </TabsTrigger>
            <TabsTrigger value="tests" className="px-2.5 text-xs">
              Test Results
            </TabsTrigger>
            <TabsTrigger value="stack-trace" className="px-2.5 text-xs">
              Problems / Stack Trace
            </TabsTrigger>
            <TabsTrigger value="commit" className="px-2.5 text-xs">
              Git / Commits
            </TabsTrigger>
          </TabsList>

          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={collapsed ? "Expand bottom dock" : "Collapse bottom dock"}
            onClick={() => setCollapsed((c) => !c)}
            className="size-6"
          >
            {collapsed ? (
              <ChevronUpIcon className="size-3.5" aria-hidden="true" />
            ) : (
              <ChevronDownIcon className="size-3.5" aria-hidden="true" />
            )}
          </Button>
        </div>

        {!collapsed && (
          <div className="h-56 overflow-auto p-2">
            <TabsContent value="terminal" className="mt-0 h-full">
              <TerminalOutput
                command={terminalCommand}
                stdout={terminalStdout}
                stderr={terminalStderr}
                exitCode={terminalExitCode}
                isRunning={isExecuting}
                onExecute={onExecuteCommand}
                onClear={onClearTerminal}
                className="my-0 h-full"
              />
            </TabsContent>

            <TabsContent value="tests" className="mt-0">
              {testSummary ? (
                <TestResults
                  suite={testSummary.suite}
                  passed={testSummary.passed}
                  failed={testSummary.failed}
                  skipped={testSummary.skipped}
                  cases={testSummary.cases}
                />
              ) : (
                <div className="p-3 text-xs text-muted-foreground">
                  Run tests in the Terminal (e.g., pytest or vitest) to inspect results here.
                </div>
              )}
            </TabsContent>

            <TabsContent value="stack-trace" className="mt-0">
              {stackTrace ? (
                <StackTrace
                  errorType={stackTrace.errorType}
                  message={stackTrace.message}
                  frames={stackTrace.frames}
                  rawTrace={stackTrace.rawTrace}
                  onOpenFile={onOpenFile}
                />
              ) : (
                <div className="p-3 text-xs text-muted-foreground">
                  No stack traces or compiler errors detected.
                </div>
              )}
            </TabsContent>

            <TabsContent value="commit" className="mt-0 space-y-2">
              {commits.length > 0 ? (
                commits.map((c) => (
                  <Commit
                    key={c.hash}
                    hash={c.hash}
                    message={c.message}
                    branch={c.branch}
                    files={c.files}
                  />
                ))
              ) : (
                <div className="p-3 text-xs text-muted-foreground">
                  No git commits recorded in this session yet.
                </div>
              )}
            </TabsContent>
          </div>
        )}
      </Tabs>
    </div>
  );
}
