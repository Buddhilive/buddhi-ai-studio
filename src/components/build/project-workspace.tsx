"use client";

import * as React from "react";
import Link from "next/link";
import type { UIMessage } from "ai";
import {
  ArrowLeftIcon,
  BoxIcon,
  Code2Icon,
  Loader2Icon,
  MessageSquareIcon,
  RefreshCwIcon,
  RouteIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ChatInterface from "@/components/chat/chat-interface";
import { TrajectoryPanel } from "@/components/trajectory/trajectory-panel";
import { IdeWorkspace } from "@/components/ide/ide-workspace";
import { extractTrajectoryEventsFromMessages } from "@/hooks/use-trajectory-stream";
import type { BuildProjectSummary } from "@/components/build/build-dashboard";
import {
  ProjectWorkspaceProvider,
  type OpenInIdeTarget,
  type WorkspaceTab,
} from "@/components/build/project-workspace-context";
import { cn } from "@/lib/utils";

interface ProjectWorkspaceProps {
  projectId: string;
  ideSlot?: React.ReactNode;
}

export function ProjectWorkspace({ projectId, ideSlot }: ProjectWorkspaceProps) {
  const [project, setProject] = React.useState<BuildProjectSummary | null>(null);
  const [sessionId, setSessionId] = React.useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = React.useState<"connecting" | "running" | "disconnected">(
    "connecting"
  );
  const [hydratedFrom, setHydratedFrom] = React.useState<string | null>(null);
  const [initialMessages, setInitialMessages] = React.useState<UIMessage[]>([]);
  const [initialPrompt, setInitialPrompt] = React.useState<string | undefined>(undefined);

  const [activeTab, setActiveTab] = React.useState<WorkspaceTab>("conversation");
  const [ideTarget, setIdeTarget] = React.useState<OpenInIdeTarget | null>(null);
  const [liveMessages, setLiveMessages] = React.useState<UIMessage[]>([]);
  const [chatStatus, setChatStatus] = React.useState<string>("ready");

  const startOrRestore = React.useCallback(async () => {
    try {
      const [startRes, histRes] = await Promise.all([
        fetch(`/api/build/projects/${encodeURIComponent(projectId)}/start`, {
          method: "POST",
        }),
        fetch(`/api/build/projects/${encodeURIComponent(projectId)}/history`),
      ]);

      if (startRes.ok) {
        const data = await startRes.json();
        setProject(data.project ?? null);
        setSessionId(data.session_id ?? null);
        setHydratedFrom(data.hydrated_from ?? null);
        setSessionStatus(data.session_id ? "running" : "disconnected");
      } else {
        setSessionStatus("disconnected");
        toast.error("Failed to start OpenSandbox for project");
      }

      if (histRes.ok) {
        const hist = await histRes.json();
        if (Array.isArray(hist.messages) && hist.messages.length > 0) {
          setInitialMessages(hist.messages);
          setLiveMessages(hist.messages);
        }
      }
    } catch {
      setSessionStatus("disconnected");
    }
  }, [projectId]);

  React.useEffect(() => {
    let active = true;
    try {
      const key = `buddhi:initial-prompt:${projectId}`;
      const stored = window.sessionStorage.getItem(key);
      if (stored) {
        window.sessionStorage.removeItem(key);
        queueMicrotask(() => {
          if (active) setInitialPrompt(stored);
        });
      }
    } catch {
      // ignore
    }
    queueMicrotask(() => {
      if (active) void startOrRestore();
    });
    return () => {
      active = false;
    };
  }, [projectId, startOrRestore]);

  const openInIde = React.useCallback((target: OpenInIdeTarget) => {
    setIdeTarget({ ...target, nonce: Date.now() });
    setActiveTab("ide");
  }, []);

  const handleMessagesChange = React.useCallback((msgs: UIMessage[], st: string) => {
    setLiveMessages(msgs);
    setChatStatus(st);
  }, []);

  const trajectoryEvents = React.useMemo(
    () => extractTrajectoryEventsFromMessages(liveMessages),
    [liveMessages]
  );

  const contextValue = React.useMemo(
    () => ({
      project,
      sessionId,
      sessionStatus,
      hydratedFrom,
      activeTab,
      setActiveTab,
      ideTarget,
      openInIde,
      restartSandbox: startOrRestore,
    }),
    [project, sessionId, sessionStatus, hydratedFrom, activeTab, ideTarget, openInIde, startOrRestore]
  );

  return (
    <ProjectWorkspaceProvider value={contextValue}>
      <div className="flex h-[calc(100vh-56px)] flex-col overflow-hidden">
        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as WorkspaceTab)}
          className="flex min-h-0 flex-1 flex-col gap-0"
        >
          {/* Top Workspace Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-4 py-1.5">
            <div className="flex items-center gap-3">
              <Link
                href="/build"
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <ArrowLeftIcon className="size-3.5" aria-hidden="true" />
                <span>Build</span>
              </Link>
              <span className="text-sm font-semibold tracking-tight">
                {project?.name || projectId}
              </span>
              {project && (
                <Badge variant="outline" className="hidden text-[11px] sm:inline-flex">
                  {project.db_dialect}
                </Badge>
              )}
            </div>

            <TabsList variant="line">
              <TabsTrigger value="conversation" className="gap-1.5">
                <MessageSquareIcon className="size-3.5" aria-hidden="true" />
                <span>Conversation</span>
              </TabsTrigger>
              <TabsTrigger value="trajectory" className="gap-1.5">
                <RouteIcon className="size-3.5" aria-hidden="true" />
                <span>
                  Trajectory{trajectoryEvents.length > 0 ? ` (${trajectoryEvents.length})` : ""}
                </span>
              </TabsTrigger>
              <TabsTrigger value="ide" className="gap-1.5">
                <Code2Icon className="size-3.5" aria-hidden="true" />
                <span>IDE</span>
              </TabsTrigger>
            </TabsList>

            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={cn(
                  "gap-1.5 text-[11px]",
                  sessionStatus === "running" &&
                    "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
                  sessionStatus === "connecting" &&
                    "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400",
                  sessionStatus === "disconnected" &&
                    "border-destructive/40 bg-destructive/10 text-destructive"
                )}
              >
                {sessionStatus === "connecting" ? (
                  <Loader2Icon className="size-3 animate-spin" aria-hidden="true" />
                ) : (
                  <BoxIcon className="size-3" aria-hidden="true" />
                )}
                <span>
                  {sessionStatus === "running"
                    ? "Sandbox Ready"
                    : sessionStatus === "connecting"
                      ? "Starting Sandbox..."
                      : "Disconnected"}
                </span>
              </Badge>

              {sessionStatus === "disconnected" && (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => void startOrRestore()}
                  className="h-7 gap-1 px-2 text-xs"
                >
                  <RefreshCwIcon className="size-3" aria-hidden="true" />
                  <span>Restart Sandbox</span>
                </Button>
              )}
            </div>
          </div>

          {/* Keep Conversation mounted via CSS visibility so streaming never aborts on tab switch */}
          <TabsContent
            value="conversation"
            keepMounted
            className={cn(
              "min-h-0 flex-1 flex-col",
              activeTab === "conversation" ? "flex" : "hidden"
            )}
          >
            <ChatInterface
              projectId={projectId}
              sessionId={sessionId}
              initialMessages={initialMessages}
              initialPrompt={initialPrompt}
              embedded
              onOpenInIde={openInIde}
              onMessagesChange={handleMessagesChange}
            />
          </TabsContent>

          <TabsContent value="trajectory" className="min-h-0 flex-1">
            <TrajectoryPanel
              events={trajectoryEvents}
              mode="live"
              isStreaming={chatStatus === "streaming" || chatStatus === "submitted"}
            />
          </TabsContent>

          <TabsContent value="ide" className="min-h-0 flex-1">
            {ideSlot ?? <IdeWorkspace projectId={projectId} />}
          </TabsContent>
        </Tabs>
      </div>
    </ProjectWorkspaceProvider>
  );
}
