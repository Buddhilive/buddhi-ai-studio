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
  | "egm.gate.pause"
  | "harness.propose"
  | "harness.probe"
  | "harness.compose"
  | "harness.distill";

export type HarnessComponentKey =
  | "system_prompt"
  | "guardrails"
  | "memory"
  | "tool_guidance"
  | "subagents"
  | "skills"
  | "scripts"
  | "plugins";

export interface HarnessComponents {
  system_prompt: string;
  guardrails: string;
  memory: string;
  tool_guidance: string;
  subagents: string;
  skills: Record<string, string>;
  scripts: Record<string, string>;
  plugins: Array<Record<string, unknown>>;
}

export interface HarnessOverlay {
  version_id: string;
  workspace_id: string;
  parent_version_id?: string | null;
  components: HarnessComponents;
  is_active: boolean;
  is_pinned: boolean;
  source_run_id?: string | null;
  created_at: string;
}

export interface ProbeResult {
  probe_id: string;
  candidate_id: string;
  target_components: string[];
  status: "passed" | "failed" | "timed_out" | "guardrail_blocked";
  steps_taken: number;
  tool_error_count: number;
  test_pass_rate: number;
  wall_clock_ms: number;
  trajectory_summary: string;
  guardrail_violations: string[];
}

export interface ExperienceEntry {
  entry_id: string;
  workspace_id: string;
  task_signature: string;
  lesson: string;
  evidence_run_id: string;
  components_affected: string[];
  confidence_score: number;
  is_pinned: boolean;
  created_at: string;
}

export interface HarnessSettings {
  enabled: boolean;
  auto_calibrate_uncalibrated: boolean;
  auto_calibrate_on_retry: boolean;
  max_calibration_rounds: number;
  max_candidates: number;
  probe_concurrency: number;
  probe_max_steps: number;
  probe_timeout_s: number;
  experience_max_entries: number;
}

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
