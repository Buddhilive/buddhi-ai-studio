export type AgentEventType =
  | "run.start"
  | "node.start"
  | "node.end"
  | "reasoning.delta"
  | "text.delta"
  | "plan.update"
  | "tool.call"
  | "tool.result"
  | "error"
  | "run.end";

export interface PlanStep {
  id: string;
  title: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  details?: string | null;
}

export interface ToolCallData {
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown> | string;
}

export interface ToolResultData {
  tool_call_id: string;
  tool_name: string;
  status: "completed" | "error" | "timeout";
  output: string;
  exit_code: number;
  truncated: boolean;
}

export interface AgentEvent {
  event: AgentEventType;
  run_id: string;
  node?: string | null;
  data: Record<string, unknown>;
  timestamp: number;
}
