"use client";

import * as React from "react";
import { TerminalOutput } from "@/components/ai-elements/terminal";
import { ToolCard } from "@/components/ai-elements/tool";
import { Plan } from "@/components/ai-elements/plan";
import { EgmPhaseBadge } from "@/components/ai-elements/egm-phase-badge";
import { EgmReviewPanel } from "@/components/ai-elements/egm-review-panel";
import { HarnessCalibrationCard } from "@/components/ai-elements/harness-calibration-card";
import { Agent, type AgentRole } from "@/components/ai-elements/agent";
import { Artifact } from "@/components/ai-elements/artifact";
import { Commit, type CommitFileChange } from "@/components/ai-elements/commit";
import {
  EnvironmentVariables,
  parseDotEnv,
} from "@/components/ai-elements/environment-variables";
import { FileTree, type FileTreeNode } from "@/components/ai-elements/file-tree";
import { JSXPreview } from "@/components/ai-elements/jsx-preview";
import { PackageInfo } from "@/components/ai-elements/package-info";
import { Sandbox } from "@/components/ai-elements/sandbox";
import { SchemaDisplay, type SchemaTable } from "@/components/ai-elements/schema-display";
import { Snippet } from "@/components/ai-elements/snippet";
import { StackTrace, parseStackTrace } from "@/components/ai-elements/stack-trace";
import { TestResults, type TestCaseResult } from "@/components/ai-elements/test-results";
import { WebPreview } from "@/components/ai-elements/web-preview";
import type { PlanStep, EgmReviewReport } from "@/lib/agent-events";
import type { OpenInIdeTarget } from "@/components/build/project-workspace-context";

interface AgentPartProps {
  part: Record<string, unknown>;
  onOpenInIde?: (target: OpenInIdeTarget) => void;
}

function parseJsonSafe(raw: unknown): Record<string, unknown> | null {
  if (raw && typeof raw === "object") return raw as Record<string, unknown>;
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
    } catch {
      return null;
    }
  }
  return null;
}

function buildTreeFromLines(lines: string[]): FileTreeNode[] {
  const root: Record<string, FileTreeNode> = {};
  for (const raw of lines) {
    const clean = raw.trim().replace(/^\.\//, "");
    if (!clean) continue;
    const parts = clean.split("/").filter(Boolean);
    let level = root;
    const acc: string[] = [];
    parts.forEach((part, idx) => {
      acc.push(part);
      const full = acc.join("/");
      const isFile = idx === parts.length - 1;
      if (!level[part]) {
        level[part] = {
          name: part,
          path: full,
          type: isFile ? "file" : "directory",
          children: [],
        };
      }
      if (!isFile) {
        level[part].type = "directory";
        const childMap: Record<string, FileTreeNode> = {};
        for (const c of level[part].children || []) childMap[c.name] = c;
        level = childMap;
      }
    });
  }
  return Object.values(root);
}

export function AgentMessagePart({ part, onOpenInIde }: AgentPartProps) {
  if (part.type === "data-plan" && Array.isArray(part.data)) {
    return <Plan steps={part.data as PlanStep[]} />;
  }

  if (part.type === "data-agent-status" && part.data && typeof part.data === "object") {
    const d = part.data as Record<string, unknown>;
    return (
      <Agent
        name={typeof d.name === "string" ? d.name : undefined}
        role={(d.role as AgentRole) || "assistant"}
        model={typeof d.model === "string" ? d.model : undefined}
        status={(d.status as "idle" | "running" | "completed" | "error") || "running"}
        stepLabel={typeof d.step === "string" ? d.step : undefined}
        tokenCount={typeof d.tokens === "number" ? d.tokens : undefined}
      />
    );
  }

  if (part.type === "data-artifact" && part.data && typeof part.data === "object") {
    const d = part.data as Record<string, unknown>;
    return (
      <Artifact
        title={String(d.title || "Artifact")}
        description={typeof d.description === "string" ? d.description : undefined}
        filePath={typeof d.file_path === "string" ? d.file_path : undefined}
        content={String(d.content || "")}
        language={typeof d.language === "string" ? d.language : undefined}
        onOpenInIde={onOpenInIde ? (fp) => onOpenInIde({ filePath: fp }) : undefined}
      />
    );
  }

  if (part.type === "data-commit" && part.data && typeof part.data === "object") {
    const d = part.data as Record<string, unknown>;
    return (
      <Commit
        hash={String(d.hash || "0000000")}
        message={String(d.message || "Update workspace")}
        author={typeof d.author === "string" ? d.author : undefined}
        branch={typeof d.branch === "string" ? d.branch : undefined}
        timestamp={typeof d.timestamp === "string" ? d.timestamp : undefined}
        files={Array.isArray(d.files) ? (d.files as CommitFileChange[]) : []}
      />
    );
  }

  if (part.type === "data-sandbox-status" && part.data && typeof part.data === "object") {
    const d = part.data as Record<string, unknown>;
    return (
      <Sandbox
        sessionId={typeof d.session_id === "string" ? d.session_id : undefined}
        runtimeImage={typeof d.runtime_image === "string" ? d.runtime_image : undefined}
        status={(d.status as "running" | "connecting" | "disconnected") || "running"}
        executionTimeMs={typeof d.execution_time_ms === "number" ? d.execution_time_ms : undefined}
      />
    );
  }

  if (part.type === "data-schema" && part.data && typeof part.data === "object") {
    const d = part.data as Record<string, unknown>;
    return (
      <SchemaDisplay
        dialect={typeof d.dialect === "string" ? d.dialect : "postgresql"}
        tables={Array.isArray(d.tables) ? (d.tables as SchemaTable[]) : []}
      />
    );
  }

  if (part.type === "data-test-results" && part.data && typeof part.data === "object") {
    const d = part.data as Record<string, unknown>;
    return (
      <TestResults
        suite={typeof d.suite === "string" ? d.suite : undefined}
        passed={Number(d.passed ?? 0)}
        failed={Number(d.failed ?? 0)}
        skipped={Number(d.skipped ?? 0)}
        durationMs={typeof d.duration_ms === "number" ? d.duration_ms : undefined}
        cases={Array.isArray(d.cases) ? (d.cases as TestCaseResult[]) : []}
      />
    );
  }

  if (part.type === "data-egm-status" && part.data && typeof part.data === "object") {
    const data = part.data as Record<string, unknown>;
    const phase = (data.phase as string) || (data.stage as string) || "draft";
    const round = typeof data.round === "number" ? data.round : 1;
    const maxRounds = typeof data.max_rounds === "number" ? data.max_rounds : 3;
    const reviewerStatuses =
      (data.reviewer_statuses as Record<string, string>) ||
      (data.persona && data.status ? { [String(data.persona)]: String(data.status) } : {});
    const specPath = typeof data.spec_path === "string" ? data.spec_path : undefined;

    return (
      <EgmPhaseBadge
        phase={phase}
        round={round}
        maxRounds={maxRounds}
        reviewerStatuses={reviewerStatuses}
        specPath={specPath}
      />
    );
  }

  if (part.type === "data-egm-review" && part.data && typeof part.data === "object") {
    const data = part.data as Record<string, unknown>;
    const report = (data.review_report as EgmReviewReport) || null;
    const runId = (data.run_id as string) || "";
    const specContract = data.spec_contract as { path?: string } | undefined;

    if (report) {
      return (
        <EgmReviewPanel
          runId={runId}
          report={report}
          specPath={specContract?.path}
        />
      );
    }
  }

  if (part.type === "data-harness-status" && part.data && typeof part.data === "object") {
    const data = part.data as Record<string, unknown>;
    return (
      <HarnessCalibrationCard
        event={String(data.event ?? "harness.propose")}
        data={data}
      />
    );
  }

  const partType = typeof part.type === "string" ? part.type : "";
  if (partType === "tool-invocation" || partType.startsWith("tool-")) {
    const toolInvocation = (part.toolInvocation as Record<string, unknown>) || part;
    const toolName = (toolInvocation.toolName as string) || (part.toolName as string) || "tool";
    const rawArgs = toolInvocation.args || toolInvocation.input || part.input || {};
    const argsObj = parseJsonSafe(rawArgs) || {};
    const state = toolInvocation.state || (toolInvocation.output !== undefined ? "result" : "call");
    const output =
      typeof toolInvocation.output === "string"
        ? toolInvocation.output
        : toolInvocation.result
          ? String(toolInvocation.result)
          : undefined;

    if (toolName === "write_file" || toolName === "read_file") {
      const filePath = typeof argsObj.path === "string" ? argsObj.path : "workspace-file";
      const content =
        toolName === "write_file" && typeof argsObj.content === "string"
          ? argsObj.content
          : output || "";

      if (filePath.endsWith(".env") || filePath.endsWith(".env.local")) {
        return <EnvironmentVariables source={filePath} variables={parseDotEnv(content)} />;
      }
      if (filePath.endsWith("package.json")) {
        const pkg = parseJsonSafe(content);
        if (pkg) {
          return (
            <PackageInfo
              name={String(pkg.name || "package.json")}
              version={typeof pkg.version === "string" ? pkg.version : undefined}
              dependencies={(pkg.dependencies as Record<string, string>) || {}}
              devDependencies={(pkg.devDependencies as Record<string, string>) || {}}
              scripts={(pkg.scripts as Record<string, string>) || {}}
            />
          );
        }
      }
      if (filePath.endsWith(".jsx") && content.trim().startsWith("<")) {
        return <JSXPreview title={filePath} jsx={content} />;
      }

      return (
        <Artifact
          title={filePath}
          description={toolName === "write_file" ? "File written to OpenSandbox" : "File read from OpenSandbox"}
          filePath={filePath}
          content={content}
          language={filePath.split(".").pop()}
          onOpenInIde={onOpenInIde ? (fp) => onOpenInIde({ filePath: fp }) : undefined}
        />
      );
    }

    if (toolName === "list_files" && output) {
      const nodes = buildTreeFromLines(output.split(/\r?\n/));
      return (
        <FileTree
          nodes={nodes}
          onSelectFile={onOpenInIde ? (fp) => onOpenInIde({ filePath: fp }) : undefined}
        />
      );
    }

    if (toolName === "run_python_repl") {
      return (
        <Sandbox
          status={state === "result" ? "completed" : "running"}
          stdout={output}
        />
      );
    }

    if (toolName === "provision_postgres_db") {
      const parsed = parseJsonSafe(output);
      if (parsed) {
        const envVars = Object.entries(parsed)
          .filter(([, v]) => typeof v === "string" || typeof v === "number")
          .map(([k, v]) => ({ key: k.toUpperCase(), value: String(v) }));
        if (envVars.length > 0) {
          return <EnvironmentVariables source="provision_postgres_db" variables={envVars} />;
        }
      }
    }

    if ((toolName === "drizzle_kit" || toolName === "query_database") && output) {
      const parsed = parseJsonSafe(output);
      if (parsed && Array.isArray(parsed.tables)) {
        return (
          <SchemaDisplay
            dialect={typeof argsObj.dialect === "string" ? argsObj.dialect : "postgresql"}
            tables={parsed.tables as SchemaTable[]}
          />
        );
      }
    }

    if (toolName === "run_command") {
      const commandStr =
        typeof argsObj.command === "string" ? argsObj.command : String(rawArgs);

      if (output) {
        if (/Traceback \(most recent call last\)|error TS\d+:/i.test(output)) {
          const parsedTrace = parseStackTrace(output);
          return (
            <StackTrace
              errorType={parsedTrace.errorType}
              message={parsedTrace.message}
              frames={parsedTrace.frames}
              rawTrace={output}
              onOpenFile={
                onOpenInIde ? (file, line) => onOpenInIde({ filePath: file, line }) : undefined
              }
            />
          );
        }

        const pytestMatch = output.match(/(\d+)\s+passed(?:,\s+(\d+)\s+failed)?/i);
        if (pytestMatch) {
          return (
            <TestResults
              suite={commandStr}
              passed={Number(pytestMatch[1])}
              failed={Number(pytestMatch[2] || 0)}
            />
          );
        }

        const commitMatch = output.match(/\[([^\s\]]+)\s+([a-f0-9]{7,40})\]\s+(.+)/i);
        if (commitMatch) {
          return (
            <Commit
              branch={commitMatch[1]}
              hash={commitMatch[2]}
              message={commitMatch[3]}
            />
          );
        }

        const urlMatch = output.match(/https?:\/\/(?:localhost|127\.0\.0\.1):\d+[^\s]*/i);
        if (urlMatch) {
          return (
            <div className="space-y-2">
              <Snippet label="Dev Server" code={urlMatch[0]} />
              <WebPreview url={urlMatch[0]} />
            </div>
          );
        }
      }

      return (
        <TerminalOutput
          command={commandStr}
          stdout={output || ""}
          exitCode={state === "result" && output ? 0 : undefined}
        />
      );
    }

    return (
      <ToolCard
        toolName={toolName}
        toolCallId={(toolInvocation.toolCallId as string) || (part.toolCallId as string)}
        argumentsText={typeof rawArgs === "object" && rawArgs !== null ? (rawArgs as Record<string, unknown>) : String(rawArgs)}
        output={output}
        status={state === "result" ? "completed" : "running"}
      />
    );
  }

  return null;
}
