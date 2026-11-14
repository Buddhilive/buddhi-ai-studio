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
  | "run.end"
  | "egm.phase"
  | "egm.reviewer.status"
  | "egm.artifact"
  | "egm.gate.pause";

export interface EgmFinding {
  id: string;
  lens: string;
  severity: "blocker" | "major" | "nit";
  scope: string;
  description: string;
  recommendation: string;
  decision?: "accept" | "reject" | "defer";
  rationale?: string;
}

export interface EgmReviewerStatus {
  stage: string;
  persona: string;
  status: "running" | "retrying" | "completed" | "not run";
  round: number;
  findings_count?: number | null;
}

export interface EgmReviewReport {
  round: number;
  artifact_path: string;
  reviewer_statuses: Record<string, "running" | "retrying" | "completed" | "not run">;
  findings: EgmFinding[];
}

export interface SpecContract {
  path: string;
  content: string;
  feature_range?: [number, number];
  detailed_range?: [number, number];
  target_scope_files: string[];
  approved: boolean;
}

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
