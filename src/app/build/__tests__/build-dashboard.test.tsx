import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BuildDashboard } from "@/components/build/build-dashboard";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

describe("BuildDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("renders empty state when no projects exist", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    } as Response);

    render(<BuildDashboard />);

    expect(await screen.findByText("No projects yet")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /create new/i }).length).toBeGreaterThanOrEqual(1);
  });

  it("toggles between Grid and List view and creates a new project", async () => {
    const user = userEvent.setup();
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            id: "proj-1",
            name: "Alpha App",
            description: "First app",
            template: "nextjs-vibe",
            db_dialect: "postgresql",
            active_session_id: "sess-1",
            session_active: true,
            runtime_image: "buddhilive/vibe-sandbox:latest",
            created_at: "2026-11-15T10:00:00Z",
            updated_at: "2026-11-15T10:00:00Z",
          },
        ],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          project: { id: "new-proj-9" },
          session_id: "sess-new",
        }),
      } as Response);

    render(<BuildDashboard />);

    expect(await screen.findByText("Alpha App")).toBeTruthy();
    expect(screen.getByTestId("projects-grid")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /list view/i }));
    expect(screen.getByTestId("projects-list")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /create new/i }));
    const nameInput = await screen.findByLabelText(/project name/i);
    await user.type(nameInput, "New Project");
    await user.click(screen.getByRole("button", { name: /create & start/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/build/project/new-proj-9");
    });
  });
});
