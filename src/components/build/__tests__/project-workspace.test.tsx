import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectWorkspace } from "@/components/build/project-workspace";

vi.mock("@/components/chat/chat-interface", () => ({
  default: ({ onOpenInIde }: { onOpenInIde?: (t: { filePath: string }) => void }) => (
    <div>
      <div>Mock Chat Interface</div>
      <button type="button" onClick={() => onOpenInIde?.({ filePath: "src/app.tsx" })}>
        Open in IDE
      </button>
    </div>
  ),
}));

vi.mock("@/components/trajectory/trajectory-panel", () => ({
  TrajectoryPanel: () => <div>Mock Trajectory Panel</div>,
}));

describe("ProjectWorkspace & IDE", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("switches between Conversation, Trajectory, and IDE tabs, edits & saves file with Ctrl+S, and handles Open in IDE", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/start")) {
        return {
          ok: true,
          json: async () => ({
            project: {
              id: "proj-1",
              name: "Demo App",
              description: "",
              template: "nextjs-vibe",
              db_dialect: "postgresql",
              active_session_id: "sess-1",
              session_active: true,
              runtime_image: "buddhilive/vibe-sandbox:latest",
              created_at: "2026-11-15T10:00:00Z",
              updated_at: "2026-11-15T10:00:00Z",
            },
            session_id: "sess-1",
            hydrated_from: "template",
          }),
        } as Response;
      }
      if (url.endsWith("/history")) {
        return {
          ok: true,
          json: async () => ({ messages: [], trajectory_events: [] }),
        } as Response;
      }
      if (url.endsWith("/files") && (!init || init.method !== "PUT")) {
        return {
          ok: true,
          json: async () => ({
            project_id: "proj-1",
            root: "/workspace",
            files: ["src/app.tsx"],
            tree: [
              {
                name: "src",
                path: "src",
                type: "directory",
                children: [{ name: "app.tsx", path: "src/app.tsx", type: "file" }],
              },
            ],
          }),
        } as Response;
      }
      if (url.includes("/files/src/app.tsx")) {
        return {
          ok: true,
          json: async () => ({
            project_id: "proj-1",
            path: "src/app.tsx",
            content: "export const a = 1;",
            size: 19,
          }),
        } as Response;
      }
      if (url.endsWith("/files") && init?.method === "PUT") {
        return {
          ok: true,
          json: async () => ({
            project_id: "proj-1",
            path: "src/app.tsx",
            saved: true,
            synced_to_storage: true,
          }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    });

    global.fetch = fetchMock as unknown as typeof fetch;

    render(<ProjectWorkspace projectId="proj-1" />);

    expect(await screen.findByText("Demo App")).toBeTruthy();
    expect(screen.getByRole("tab", { name: /conversation/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /trajectory/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /ide/i })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /open in ide/i }));
    const editor = (await screen.findByLabelText("Code editor for src/app.tsx")) as HTMLTextAreaElement;
    expect(editor.value).toBe("export const a = 1;");

    await user.type(editor, "\nexport const b = 2;");
    await user.keyboard("{Control>}s{/Control}");

    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(
        ([u, i]) => String(u).endsWith("/files") && (i as RequestInit)?.method === "PUT"
      );
      expect(putCall).toBeTruthy();
    });
  });
});
