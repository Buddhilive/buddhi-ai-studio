import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AgentMessagePart } from "@/components/chat/agent-parts";

describe("AgentMessagePart dispatch", () => {
  it("dispatches data-agent-status, write_file, list_files, and run_command outputs", async () => {
    const user = userEvent.setup();
    const onOpenInIde = vi.fn();

    render(
      <div>
        <AgentMessagePart
          part={{
            type: "data-agent-status",
            data: { role: "goldfish", model: "gemma-4-e4b", status: "completed" },
          }}
        />
        <AgentMessagePart
          part={{
            type: "tool-invocation",
            toolName: "write_file",
            args: { path: "src/index.ts", content: "export const x = 1;" },
            state: "result",
            output: "ok",
          }}
          onOpenInIde={onOpenInIde}
        />
        <AgentMessagePart
          part={{
            type: "tool-invocation",
            toolName: "run_command",
            args: { command: "pytest" },
            state: "result",
            output: "5 passed, 0 failed in 0.2s",
          }}
        />
        <AgentMessagePart
          part={{
            type: "tool-invocation",
            toolName: "run_command",
            args: { command: "tsc --noEmit" },
            state: "result",
            output: "src/index.ts(4,10): error TS2304: Cannot find name 'foo'.",
          }}
          onOpenInIde={onOpenInIde}
        />
      </div>
    );

    expect(screen.getAllByText("Goldfish Reviewer").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("5 passed")).toBeTruthy();
    expect(screen.getByText("TS2304")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /open in ide/i }));
    expect(onOpenInIde).toHaveBeenCalledWith({ filePath: "src/index.ts" });
  });
});
