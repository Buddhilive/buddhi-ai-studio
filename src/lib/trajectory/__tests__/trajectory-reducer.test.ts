import { describe, expect, it } from "vitest";
import { buildTrajectoryTurns } from "@/lib/trajectory-stream";
import type { AgentEvent } from "@/lib/agent-events";

describe("buildTrajectoryTurns", () => {
  it("coalesces reasoning/text deltas and pairs tool calls with incremental shell output", () => {
    const events: AgentEvent[] = [
      {
        event: "turn.start",
        run_id: "run_1",
        seq: 1,
        timestamp_ms: 1000,
        turn_id: "turn_1",
        data: { turn_id: "turn_1", turn_index: 1, prompt_preview: "Run tests" },
        timestamp: 1,
      },
      {
        event: "reasoning.delta",
        run_id: "run_1",
        seq: 2,
        timestamp_ms: 1010,
        turn_id: "turn_1",
        node: "reason",
        data: { delta: "Let me " },
        timestamp: 1.01,
      },
      {
        event: "reasoning.delta",
        run_id: "run_1",
        seq: 3,
        timestamp_ms: 1020,
        turn_id: "turn_1",
        node: "reason",
        data: { delta: "run pytest." },
        timestamp: 1.02,
      },
      {
        event: "tool.args.delta",
        run_id: "run_1",
        seq: 4,
        timestamp_ms: 1030,
        turn_id: "turn_1",
        node: "act",
        data: { tool_call_id: "tc_1", tool_name: "run_command", delta: '{"command":"pytest"}' },
        timestamp: 1.03,
      },
      {
        event: "tool.output.delta",
        run_id: "run_1",
        seq: 5,
        timestamp_ms: 1040,
        turn_id: "turn_1",
        node: "observe",
        data: { tool_call_id: "tc_1", tool_name: "run_command", stream: "stdout", delta: "collected 3 items\n" },
        timestamp: 1.04,
      },
      {
        event: "tool.output.delta",
        run_id: "run_1",
        seq: 6,
        timestamp_ms: 1050,
        turn_id: "turn_1",
        node: "observe",
        data: { tool_call_id: "tc_1", tool_name: "run_command", stream: "stderr", delta: "warn: deprec\n" },
        timestamp: 1.05,
      },
      {
        event: "tool.result",
        run_id: "run_1",
        seq: 7,
        timestamp_ms: 1100,
        turn_id: "turn_1",
        node: "observe",
        data: { tool_call_id: "tc_1", tool_name: "run_command", status: "completed", output: "3 passed", exit_code: 0 },
        timestamp: 1.1,
      },
      // Duplicate seq=5 should be deduplicated on reconnect
      {
        event: "tool.output.delta",
        run_id: "run_1",
        seq: 5,
        timestamp_ms: 1040,
        turn_id: "turn_1",
        node: "observe",
        data: { tool_call_id: "tc_1", tool_name: "run_command", stream: "stdout", delta: "collected 3 items\n" },
        timestamp: 1.04,
      },
      {
        event: "turn.end",
        run_id: "run_1",
        seq: 8,
        timestamp_ms: 1120,
        turn_id: "turn_1",
        node: "observe",
        data: { turn_id: "turn_1", duration_ms: 120, status: "completed" },
        timestamp: 1.12,
      },
    ];

    const turns = buildTrajectoryTurns(events);
    expect(turns).toHaveLength(1);
    expect(turns[0].promptPreview).toBe("Run tests");
    expect(turns[0].durationMs).toBe(120);
    expect(turns[0].items).toHaveLength(2);

    const thought = turns[0].items[0];
    expect(thought.category).toBe("thought");
    expect(thought.payloadText).toBe("Let me run pytest.");
    expect(thought.status).toBe("completed");

    const shell = turns[0].items[1];
    expect(shell.category).toBe("shell");
    expect(shell.stdoutText).toBe("collected 3 items\n");
    expect(shell.stderrText).toBe("warn: deprec\n");
    expect(shell.status).toBe("completed");
    expect(shell.exitCode).toBe(0);
  });
});
