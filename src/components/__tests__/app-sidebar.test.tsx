import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";

const mockUsePathname = vi.fn(() => "/build");

vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));

beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

describe("AppSidebar navigation", () => {
  it("replaces Playground with Build and keeps Build active on project routes", () => {
    mockUsePathname.mockReturnValue("/build/project/demo-123");

    render(
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>
    );

    expect(screen.queryByText("Playground")).toBeNull();
    const buildLink = screen.getByRole("link", { name: /build/i });
    expect(buildLink.getAttribute("href")).toBe("/build");
    expect(buildLink.hasAttribute("data-active")).toBe(true);
  });
});
