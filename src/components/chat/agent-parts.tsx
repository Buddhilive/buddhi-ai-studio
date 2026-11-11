"use client";

import * as React from "react";
import { TerminalOutput } from "@/components/ai-elements/terminal";
import { ToolCard } from "@/components/ai-elements/tool";
import { Plan } from "@/components/ai-elements/plan";
import type { PlanStep } from "@/lib/agent-events";

interface AgentPartProps {
  part: Record<string, unknown>;
}

export function AgentMessagePart({ part }: AgentPartProps) {
  // Handle Plan data parts
  if (part.type === "data-plan" && Array.isArray(part.data)) {
    return <Plan steps={part.data as PlanStep[]} />;
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
