import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Agent } from "@/components/ai-elements/agent";
import { Artifact } from "@/components/ai-elements/artifact";
import { Commit } from "@/components/ai-elements/commit";
import { EnvironmentVariables } from "@/components/ai-elements/environment-variables";
import { FileTree } from "@/components/ai-elements/file-tree";
import { JSXPreview } from "@/components/ai-elements/jsx-preview";
import { PackageInfo } from "@/components/ai-elements/package-info";
import { Sandbox } from "@/components/ai-elements/sandbox";
import { SchemaDisplay } from "@/components/ai-elements/schema-display";
import { Snippet } from "@/components/ai-elements/snippet";
import { StackTrace } from "@/components/ai-elements/stack-trace";
import { TerminalOutput } from "@/components/ai-elements/terminal";
import { TestResults } from "@/components/ai-elements/test-results";
import { WebPreview } from "@/components/ai-elements/web-preview";

describe("AI Elements Core", () => {
  it("renders Agent, Artifact, Commit, PackageInfo, Sandbox, SchemaDisplay, Snippet, TerminalOutput, TestResults", () => {
    const onOpenInIde = vi.fn();
    render(
      <div>
        <Agent role="elephant" model="gemma-4-e4b" status="running" tokenCount={1200} />
        <Artifact title="spec.md" filePath="spec.md" content="# Spec" onOpenInIde={onOpenInIde} />
        <Commit hash="abc123456" message="feat: init" branch="main" files={[{ path: "a.ts", additions: 5, deletions: 1 }]} />
        <PackageInfo name="app" version="1.0.0" dependencies={{ react: "19.2.4" }} />
        <Sandbox sessionId="sess_1234567890" status="running" executionTimeMs={42} />
        <SchemaDisplay dialect="postgresql" tables={[{ name: "users", columns: [{ name: "id", type: "uuid", primaryKey: true, nullable: false }] }]} />
        <Snippet label="Run" code="pnpm dev" />
        <TerminalOutput command="echo hi" stdout="hi" exitCode={0} />
        <TestResults suite="vitest" passed={4} failed={1} cases={[{ name: "renders", status: "passed" }]} />
      </div>
    );

    expect(screen.getAllByText("Elephant Architect").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("spec.md")).toBeTruthy();
    expect(screen.getByText("feat: init")).toBeTruthy();
    expect(screen.getByText("react")).toBeTruthy();
    expect(screen.getByText("OpenSandbox")).toBeTruthy();
    expect(screen.getByText("users")).toBeTruthy();
    expect(screen.getByText("pnpm dev")).toBeTruthy();
    expect(screen.getByText("exit: 0")).toBeTruthy();
    expect(screen.getByText("4 passed")).toBeTruthy();
    expect(screen.getByText("1 failed")).toBeTruthy();
  });

  it("masks sensitive EnvironmentVariables by default and toggles reveal", async () => {
    const user = userEvent.setup();
    render(
      <EnvironmentVariables
        variables={[
          { key: "NODE_ENV", value: "development" },
          { key: "DATABASE_URL", value: "postgres://user:secretpass@localhost/db" },
          { key: "API_SECRET_KEY", value: "sk-12345" },
        ]}
      />
    );

    expect(screen.getByTestId("env-val-NODE_ENV").textContent).toBe("development");
    expect(screen.getByTestId("env-val-DATABASE_URL").textContent).toBe("••••••••");
    expect(screen.getByTestId("env-val-API_SECRET_KEY").textContent).toBe("••••••••");

    await user.click(screen.getByRole("button", { name: "Reveal API_SECRET_KEY" }));
    expect(screen.getByTestId("env-val-API_SECRET_KEY").textContent).toBe("sk-12345");
  });

  it("supports FileTree WAI-ARIA keyboard navigation and StackTrace frame click", async () => {
    const user = userEvent.setup();
    const onSelectFile = vi.fn();
    const onOpenFile = vi.fn();

    render(
      <div>
        <FileTree
          nodes={[
            {
              name: "src",
              path: "src",
              type: "directory",
              children: [{ name: "app.tsx", path: "src/app.tsx", type: "file" }],
            },
          ]}
          onSelectFile={onSelectFile}
        />
        <StackTrace
          errorType="TS2322"
          message="Type mismatch"
          frames={[{ file: "src/app.tsx", line: 12, fn: "App" }]}
          onOpenFile={onOpenFile}
        />
      </div>
    );

    const srcItem = screen.getByRole("treeitem", { name: "src" });
    srcItem.focus();
    await user.keyboard("{ArrowRight}");
    const appItem = await screen.findByRole("treeitem", { name: "app.tsx" });
    await user.keyboard("{ArrowDown}{Enter}");
    expect(appItem).toBeTruthy();
    expect(onSelectFile).toHaveBeenCalledWith("src/app.tsx");

    await user.click(screen.getByRole("button", { name: "src/app.tsx:12" }));
    expect(onOpenFile).toHaveBeenCalledWith("src/app.tsx", 12);
  });

  it("toggles JSXPreview modes and WebPreview viewports with sandboxed iframe", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <JSXPreview jsx="<div>Hello JSX</div>" />
        <WebPreview url="http://localhost:3000" />
      </div>
    );

    expect(screen.getByText("Hello JSX")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: /code/i }));
    expect(screen.getByText("<div>Hello JSX</div>")).toBeTruthy();

    const iframe = screen.getByTitle("Web Preview");
    expect(iframe.getAttribute("sandbox")).toBe("allow-scripts allow-forms allow-popups");
    await user.click(screen.getByRole("button", { name: /mobile viewport/i }));
    expect((iframe as HTMLElement).style.width).toBe("390px");
  });
});
