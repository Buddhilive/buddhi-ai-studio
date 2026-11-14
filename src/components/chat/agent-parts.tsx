"use client";

import * as React from "react";
import { TerminalOutput } from "@/components/ai-elements/terminal";
import { ToolCard } from "@/components/ai-elements/tool";
import { Plan } from "@/components/ai-elements/plan";
import { EgmPhaseBadge } from "@/components/ai-elements/egm-phase-badge";
import { EgmReviewPanel } from "@/components/ai-elements/egm-review-panel";
import { HarnessCalibrationCard } from "@/components/ai-elements/harness-calibration-card";
import type { PlanStep, EgmReviewReport } from "@/lib/agent-events";

interface AgentPartProps {
  part: Record<string, unknown>;
}

export function AgentMessagePart({ part }: AgentPartProps) {
  // Handle Plan data parts
  if (part.type === "data-plan" && Array.isArray(part.data)) {
    return <Plan steps={part.data as PlanStep[]} />;
  }

  // Handle EGM status / telemetry data parts
  if (part.type === "data-egm-status" && part.data && typeof part.data === "object") {
    const data = part.data as Record<string, unknown>;
    const phase = (data.phase as string) || (data.stage as string) || "draft";
    const round = typeof data.round === "number" ? data.round : 1;
    const maxRounds = typeof data.max_rounds === "number" ? data.max_rounds : 3;
    const reviewerStatuses = (data.reviewer_statuses as Record<string, string>) ||
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

  // Handle EGM review gate / findings triage parts
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

  // Handle Harness2 calibration / probe / compose / distill parts
  if (part.type === "data-harness-status" && part.data && typeof part.data === "object") {
    const data = part.data as Record<string, unknown>;
    return <HarnessCalibrationCard event={String(data.event ?? "harness.propose")} data={data} />;
  }

  // Handle Tool call / result parts
  const partType = typeof part.type === "string" ? part.type : "";
  if (partType === "tool-invocation" || partType.startsWith("tool-")) {
    const toolInvocation = (part.toolInvocation as Record<string, unknown>) || part;
    const toolName = (toolInvocation.toolName as string) || (part.toolName as string) || "tool";
    const args = toolInvocation.args || toolInvocation.input || part.input || {};
    const state = toolInvocation.state || (toolInvocation.output !== undefined ? "result" : "call");
    const output = typeof toolInvocation.output === "string"
      ? toolInvocation.output
      : (toolInvocation.result ? String(toolInvocation.result) : undefined);

    if (toolName === "run_command") {
      const commandStr = typeof args === "object" && args !== null && "command" in args
        ? String((args as Record<string, unknown>).command)
        : String(args);
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
        argumentsText={typeof args === "object" && args !== null ? (args as Record<string, unknown>) : String(args)}
        output={output}
        status={state === "result" ? "completed" : "running"}
      />
    );
  }

  return null;
}
