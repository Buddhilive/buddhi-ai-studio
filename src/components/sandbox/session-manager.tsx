"use client";

import * as React from "react";
import { BoxIcon, RefreshCwIcon, Trash2Icon, PlusIcon, FileTextIcon, UploadIcon, CheckIcon } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export interface SandboxSessionItem {
  session_id: string;
  runtime_image: string;
  status: "running" | "idle" | "terminated";
  created_at: string;
  last_activity_at: string;
  expires_at: string;
  allow_network: boolean;
}

interface SessionManagerProps {
  sessions: SandboxSessionItem[];
  isLoading: boolean;
  onRefresh: () => void;
  onCreateSession: (image: string) => Promise<void>;
  onTerminateSession: (sessionId: string) => Promise<void>;
}

export function SessionManager({
  sessions,
  isLoading,
  onRefresh,
  onCreateSession,
  onTerminateSession,
}: SessionManagerProps) {
  const [isCreating, setIsCreating] = React.useState(false);
  const [selectedImage, setSelectedImage] = React.useState("python:3.11-slim");
  const [activeSessionId, setActiveSessionId] = React.useState<string | null>(null);

  // File upload state for selected session
  const [filePath, setFilePath] = React.useState("");
  const [fileContent, setFileContent] = React.useState("");
  const [fileNotice, setFileNotice] = React.useState<string | null>(null);
  const [isUploading, setIsUploading] = React.useState(false);

  const handleCreate = async () => {
    setIsCreating(true);
    try {
      await onCreateSession(selectedImage);
    } finally {
      setIsCreating(false);
    }
  };

  const handleUploadFile = async () => {
    if (!activeSessionId || !filePath.trim()) return;
    setIsUploading(true);
    setFileNotice(null);
    try {
      const res = await fetch(`/api/sandbox/sessions/${activeSessionId}/files`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: filePath.trim(),
          content: fileContent,
          is_base64: false,
        }),
      });
      if (res.ok) {
        setFileNotice(`File "${filePath}" saved to workspace.`);
        setFilePath("");
        setFileContent("");
      } else {
        const err = await res.json();
        setFileNotice(`Error: ${err.detail || "Upload failed"}`);
      }
    } catch (err: unknown) {
      setFileNotice(`Error: ${String(err)}`);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Card className="border border-border/80 shadow-sm bg-card">
      <CardHeader className="py-3 px-4 border-b border-border/60 flex flex-row items-center justify-between">
        <div className="space-y-0.5">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <BoxIcon className="w-4 h-4 text-primary" />
            <span>Active Sandbox Sessions</span>
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground">
            Manage long-lived containers with persistent workspaces and sequential execution.
          </CardDescription>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-8 px-2.5 text-xs gap-1.5"
            onClick={onRefresh}
            disabled={isLoading}
          >
            <RefreshCwIcon className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>

          <Button
            size="sm"
            className="h-8 px-2.5 text-xs gap-1.5"
            onClick={handleCreate}
            disabled={isCreating}
          >
            {isCreating ? <Spinner className="w-3.5 h-3.5" /> : <PlusIcon className="w-3.5 h-3.5" />}
            <span>New Session</span>
          </Button>
        </div>
      </CardHeader>

      <CardContent className="p-4 space-y-4">
        {sessions.length === 0 ? (
          <div className="p-6 text-center text-xs text-muted-foreground border border-dashed rounded-lg">
            No active sessions. One-shot executions automatically manage ephemeral sandboxes, or click &ldquo;New Session&rdquo; above to spawn a stateful container.
          </div>
        ) : (
          <div className="border border-border/60 rounded-md overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 text-muted-foreground border-b border-border/60">
                <tr>
                  <th className="py-2 px-3 text-left font-medium">Session ID</th>
                  <th className="py-2 px-3 text-left font-medium">Image</th>
                  <th className="py-2 px-3 text-left font-medium">Status</th>
                  <th className="py-2 px-3 text-left font-medium">Last Active</th>
                  <th className="py-2 px-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono">
                {sessions.map((s) => (
                  <tr
                    key={s.session_id}
                    className={`hover:bg-muted/20 cursor-pointer ${
                      activeSessionId === s.session_id ? "bg-muted/30" : ""
                    }`}
                    onClick={() => setActiveSessionId(s.session_id)}
                  >
                    <td className="py-2 px-3 font-semibold text-foreground truncate max-w-[140px]">
                      {s.session_id.substring(0, 16)}...
                    </td>
                    <td className="py-2 px-3 text-muted-foreground">{s.runtime_image}</td>
                    <td className="py-2 px-3 font-sans">
                      <Badge variant={s.status === "running" ? "default" : "secondary"} className="text-[10px] h-4">
                        {s.status}
                      </Badge>
                    </td>
                    <td className="py-2 px-3 text-muted-foreground font-sans">
                      {new Date(s.last_activity_at).toLocaleTimeString()}
                    </td>
                    <td className="py-2 px-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-destructive hover:bg-destructive/10"
                        onClick={() => onTerminateSession(s.session_id)}
                        title="Terminate session"
                      >
                        <Trash2Icon className="w-3.5 h-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Selected session workspace inspector */}
        {activeSessionId && (
          <div className="border border-border/60 rounded-md p-3 space-y-3 bg-muted/10">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold flex items-center gap-1.5">
                <FileTextIcon className="w-3.5 h-3.5 text-primary" />
                Workspace File Inspector: <span className="font-mono text-muted-foreground">{activeSessionId.substring(0, 12)}...</span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-1.5 text-xs text-muted-foreground"
                onClick={() => setActiveSessionId(null)}
              >
                Close
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <input
                type="text"
                placeholder="Relative path (e.g. data.txt, app.py)"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                className="col-span-1 bg-background border border-border/60 rounded px-2.5 py-1 text-xs font-mono"
              />
              <input
                type="text"
                placeholder="File contents to write..."
                value={fileContent}
                onChange={(e) => setFileContent(e.target.value)}
                className="col-span-1 md:col-span-2 bg-background border border-border/60 rounded px-2.5 py-1 text-xs font-mono"
              />
            </div>

            <div className="flex items-center justify-between pt-1">
              <Button
                size="sm"
                className="h-7 text-xs gap-1.5"
                onClick={handleUploadFile}
                disabled={isUploading || !filePath.trim()}
              >
                {isUploading ? <Spinner className="w-3 h-3" /> : <UploadIcon className="w-3 h-3" />}
                <span>Write to /workspace</span>
              </Button>

              {fileNotice && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <CheckIcon className="w-3 h-3 text-emerald-500" />
                  {fileNotice}
                </span>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
