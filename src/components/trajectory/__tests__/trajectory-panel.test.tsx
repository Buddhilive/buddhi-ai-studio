import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TrajectoryPanel } from "../trajectory-panel";
import type { AgentEvent } from "@/lib/agent-events";

const SAMPLE_EVENTS: AgentEvent[] = [
  {
    event: "turn.start",
    run_id: "run_abc123",
    seq: 1,
    timestamp_ms: 1000,
    turn_id: "turn_1",
    data: { turn_id: "turn_1", turn_index: 1, prompt_preview: "Inspect config" },
    timestamp: 1,
  },
  {
    event: "reasoning.delta",
    run_id: "run_abc123",
    seq: 2,
    timestamp_ms: 1010,
    turn_id: "turn_1",
    node: "analyze",
    data: { delta: "Reading config.py first" },
    timestamp: 1.01,
  },
  {
    event: "tool.call",
    run_id: "run_abc123",
    seq: 3,
    timestamp_ms: 1020,
    turn_id: "turn_1",
    node: "act",
    data: { tool_call_id: "tc_1", tool_name: "run_command", arguments: { command: "ls -la" } },
    timestamp: 1.02,
  },
  {
    event: "tool.result",
    run_id: "run_abc123",
    seq: 4,
    timestamp_ms: 1080,
    turn_id: "turn_1",
    node: "observe",
    data: { tool_call_id: "tc_1", tool_name: "run_command", status: "completed", output: "total 4", exit_code: 0 },
    timestamp: 1.08,
  },
  {
    event: "usage.update",
    run_id: "run_abc123",
    seq: 5,
    timestamp_ms: 1090,
    turn_id: "turn_1",
    node: "analyze",
    data: { input_tokens: 120, output_tokens: 45, total_tokens: 165, duration_ms: 90 },
    timestamp: 1.09,
  },
  {
    event: "turn.end",
    run_id: "run_abc123",
    seq: 6,
    timestamp_ms: 1100,
    turn_id: "turn_1",
    node: "observe",
    data: { turn_id: "turn_1", duration_ms: 100, status: "completed" },
    timestamp: 1.1,
  },
];

describe("TrajectoryPanel", () => {
  it("filters by category and opens the inspector via keyboard", async () => {
    const user = userEvent.setup();
    render(<TrajectoryPanel events={SAMPLE_EVENTS} mode="replay" />);

    expect(screen.getByText(/120 in \/ 45 out \(165 tok\)/i)).toBeTruthy();
    expect(screen.getByText(/\[THOUGHT\]/)).toBeTruthy();
    expect(screen.getByText(/\[SHELL\]/)).toBeTruthy();

    // Filter to Shell only
    await user.click(screen.getByRole("button", { name: "Shell" }));
    expect(screen.queryByText(/\[THOUGHT\]/)).toBeNull();
    expect(screen.getByText(/\[SHELL\]/)).toBeTruthy();

    // Open inspector via keyboard
    const shellRow = screen.getByRole("button", { name: /\[SHELL\]/i });
    shellRow.focus();
    await user.keyboard("{Enter}");

    const inspector = screen.getByRole("complementary", { name: /trajectory event inspector/i });
    expect(inspector).toBeTruthy();
    expect(screen.getByText(/seq #3/)).toBeTruthy();

    // Escape closes inspector
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("complementary", { name: /trajectory event inspector/i })).toBeNull();
  });
});
