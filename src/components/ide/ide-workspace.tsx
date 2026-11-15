"use client";

import * as React from "react";
import { PanelLeftIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { IdeSidebar } from "@/components/ide/ide-sidebar";
import { IdeEditorPane, type OpenEditorFile } from "@/components/ide/ide-editor-pane";
import { IdeBottomDock } from "@/components/ide/ide-bottom-dock";
import { useProjectWorkspace, type IdeBottomDockTab } from "@/components/build/project-workspace-context";
import type { FileTreeNode } from "@/components/ai-elements/file-tree";
import { parseDotEnv, type EnvironmentVariableItem } from "@/components/ai-elements/environment-variables";
import { parseStackTrace, type StackFrame } from "@/components/ai-elements/stack-trace";

export function IdeWorkspace({ projectId }: { projectId: string }) {
  const { ideTarget } = useProjectWorkspace();

  const [tree, setTree] = React.useState<FileTreeNode[]>([]);
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const [sidebarOpenMobile, setSidebarOpenMobile] = React.useState(false);

  const [openFiles, setOpenFiles] = React.useState<OpenEditorFile[]>([]);
  const [activeFilePath, setActiveFilePath] = React.useState<string | null>(null);
  const [isSaving, setIsSaving] = React.useState(false);
  const [saveAnnouncement, setSaveAnnouncement] = React.useState("");

  const [packageData, setPackageData] = React.useState<{
    name: string;
    version?: string;
    dependencies?: Record<string, string>;
    devDependencies?: Record<string, string>;
    scripts?: Record<string, string>;
  } | null>(null);
  const [envVars, setEnvVars] = React.useState<EnvironmentVariableItem[]>([]);

  const [bottomTab, setBottomTab] = React.useState<IdeBottomDockTab>("terminal");
  const [terminalCommand, setTerminalCommand] = React.useState("");
  const [terminalStdout, setTerminalStdout] = React.useState("");
  const [terminalStderr, setTerminalStderr] = React.useState("");
  const [terminalExitCode, setTerminalExitCode] = React.useState(0);
  const [isExecuting, setIsExecuting] = React.useState(false);
  const [stackTrace, setStackTrace] = React.useState<{
    errorType: string;
    message: string;
    frames: StackFrame[];
    rawTrace?: string;
  } | null>(null);

  const fetchTree = React.useCallback(async () => {
    try {
      const res = await fetch(`/api/build/projects/${encodeURIComponent(projectId)}/files`);
      if (res.ok) {
        const data = await res.json();
        setTree(Array.isArray(data.tree) ? data.tree : []);
      }
    } catch {
      // ignore
    } finally {
      setIsRefreshing(false);
    }
  }, [projectId]);

  const handleManualRefresh = React.useCallback(() => {
    setIsRefreshing(true);
    void fetchTree();
  }, [fetchTree]);

  const openFile = React.useCallback(
    async (relPath: string) => {
      const existing = openFiles.find((f) => f.path === relPath);
      if (existing) {
        setActiveFilePath(relPath);
        return;
      }
      try {
        const encoded = relPath
          .split("/")
          .map((s) => encodeURIComponent(s))
          .join("/");
        const res = await fetch(
          `/api/build/projects/${encodeURIComponent(projectId)}/files/${encoded}`
        );
        if (!res.ok) {
          toast.error(`Failed to open ${relPath}`);
          return;
        }
        const data = await res.json();
        const content = typeof data.content === "string" ? data.content : "";
        setOpenFiles((prev) => {
          if (prev.some((p) => p.path === relPath)) return prev;
          return [...prev, { path: relPath, content, savedContent: content }];
        });
        setActiveFilePath(relPath);

        if (relPath === "package.json") {
          try {
            setPackageData(JSON.parse(content));
          } catch {
            // ignore
          }
        } else if (relPath === ".env") {
          setEnvVars(parseDotEnv(content));
        }
      } catch {
        toast.error(`Failed to open ${relPath}`);
      }
    },
    [projectId, openFiles]
  );

  React.useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) void fetchTree();
    });
    return () => {
      active = false;
    };
  }, [fetchTree]);

  React.useEffect(() => {
    if (!ideTarget) return;
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      if (ideTarget.filePath) {
        void openFile(ideTarget.filePath);
      }
      if (ideTarget.bottomTab) {
        setBottomTab(ideTarget.bottomTab);
      }
    });
    return () => {
      active = false;
    };
  }, [ideTarget, openFile]);

  const handleSaveFile = React.useCallback(
    async (path: string) => {
      const file = openFiles.find((f) => f.path === path);
      if (!file) return;
      setIsSaving(true);
      setSaveAnnouncement(`Saving ${path}...`);
      try {
        const res = await fetch(`/api/build/projects/${encodeURIComponent(projectId)}/files`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path, content: file.content }),
        });
        if (!res.ok) {
          toast.error(`Failed to save ${path}`);
          setSaveAnnouncement(`Failed to save ${path}`);
          return;
        }
        setOpenFiles((prev) =>
          prev.map((f) => (f.path === path ? { ...f, savedContent: file.content } : f))
        );
        setSaveAnnouncement(`Saved ${path}`);
        toast.success(`Saved ${path}`);
      } catch {
        toast.error(`Failed to save ${path}`);
      } finally {
        setIsSaving(false);
      }
    },
    [openFiles, projectId]
  );

  const handleExecuteCommand = React.useCallback(
    async (cmd: string) => {
      setIsExecuting(true);
      setTerminalCommand(cmd);
      try {
        const res = await fetch(
          `/api/build/projects/${encodeURIComponent(projectId)}/execute`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code: cmd, language: "bash", timeout_s: 60 }),
          }
        );
        if (res.ok) {
          const data = await res.json();
          const out = data.stdout || "";
          const err = data.stderr || "";
          setTerminalStdout(out);
          setTerminalStderr(err);
          setTerminalExitCode(typeof data.exit_code === "number" ? data.exit_code : 0);
          if (err && /Traceback|error TS\d+/i.test(err)) {
            const parsed = parseStackTrace(err);
            setStackTrace({ ...parsed, rawTrace: err });
          }
          void fetchTree();
        } else {
          setTerminalStderr("Command execution failed.");
          setTerminalExitCode(1);
        }
      } catch (err: unknown) {
        setTerminalStderr(String(err));
        setTerminalExitCode(1);
      } finally {
        setIsExecuting(false);
      }
    },
    [projectId, fetchTree]
  );

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex items-center border-b border-border bg-card px-2 py-1 lg:hidden">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setSidebarOpenMobile((o) => !o)}
          className="h-7 gap-1.5 text-xs"
        >
          <PanelLeftIcon className="size-3.5" aria-hidden="true" />
          <span>Explorer</span>
        </Button>
      </div>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className={sidebarOpenMobile ? "block h-full" : "hidden h-full lg:block"}>
          <IdeSidebar
            tree={tree}
            selectedPath={activeFilePath}
            onSelectFile={(p) => void openFile(p)}
            onRefreshFiles={handleManualRefresh}
            isRefreshing={isRefreshing}
            packageData={packageData}
            envVars={envVars}
          />
        </div>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <IdeEditorPane
            openFiles={openFiles}
            activeFilePath={activeFilePath}
            onSelectFileTab={setActiveFilePath}
            onCloseFileTab={(p) => {
              setOpenFiles((prev) => prev.filter((f) => f.path !== p));
              if (activeFilePath === p) {
                const next = openFiles.find((f) => f.path !== p);
                setActiveFilePath(next?.path ?? null);
              }
            }}
            onChangeFileContent={(p, content) =>
              setOpenFiles((prev) => prev.map((f) => (f.path === p ? { ...f, content } : f)))
            }
            onSaveFile={handleSaveFile}
            isSaving={isSaving}
            saveAnnouncement={saveAnnouncement}
            previewUrl={`/api/build/projects/${encodeURIComponent(projectId)}/preview/`}
          />

          <IdeBottomDock
            activeTab={bottomTab}
            onTabChange={setBottomTab}
            terminalCommand={terminalCommand}
            terminalStdout={terminalStdout}
            terminalStderr={terminalStderr}
            terminalExitCode={terminalExitCode}
            isExecuting={isExecuting}
            onExecuteCommand={handleExecuteCommand}
            onClearTerminal={() => {
              setTerminalStdout("");
              setTerminalStderr("");
            }}
            stackTrace={stackTrace}
            onOpenFile={(file) => void openFile(file)}
          />
        </div>
      </div>
    </div>
  );
}
