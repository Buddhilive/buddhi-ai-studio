"use client";

import * as React from "react";
import type { BuildProjectSummary } from "@/components/build/build-dashboard";

export type WorkspaceTab = "conversation" | "trajectory" | "ide";
export type IdeBottomDockTab = "terminal" | "tests" | "stack-trace" | "commit";

export interface OpenInIdeTarget {
  filePath?: string;
  line?: number;
  bottomTab?: IdeBottomDockTab;
  previewUrl?: string;
  nonce?: number;
}

interface ProjectWorkspaceContextValue {
  project: BuildProjectSummary | null;
  sessionId: string | null;
  sessionStatus: "connecting" | "running" | "disconnected";
  hydratedFrom: string | null;
  activeTab: WorkspaceTab;
  setActiveTab: (tab: WorkspaceTab) => void;
  ideTarget: OpenInIdeTarget | null;
  openInIde: (target: OpenInIdeTarget) => void;
  restartSandbox: () => Promise<void>;
}

const ProjectWorkspaceContext = React.createContext<ProjectWorkspaceContextValue | null>(null);

export function ProjectWorkspaceProvider({
  value,
  children,
}: {
  value: ProjectWorkspaceContextValue;
  children: React.ReactNode;
}) {
  return (
    <ProjectWorkspaceContext.Provider value={value}>
      {children}
    </ProjectWorkspaceContext.Provider>
  );
}

export function useProjectWorkspace() {
  const ctx = React.useContext(ProjectWorkspaceContext);
  if (!ctx) {
    throw new Error("useProjectWorkspace must be used within ProjectWorkspaceProvider");
  }
  return ctx;
}
