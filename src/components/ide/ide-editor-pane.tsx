"use client";

import * as React from "react";
import { Code2Icon, EyeIcon, GlobeIcon, SaveIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { WebPreview } from "@/components/ai-elements/web-preview";
import { JSXPreview } from "@/components/ai-elements/jsx-preview";
import { cn } from "@/lib/utils";

export interface OpenEditorFile {
  path: string;
  content: string;
  savedContent: string;
}

interface IdeEditorPaneProps {
  openFiles: OpenEditorFile[];
  activeFilePath: string | null;
  onSelectFileTab: (path: string) => void;
  onCloseFileTab: (path: string) => void;
  onChangeFileContent: (path: string, content: string) => void;
  onSaveFile: (path: string) => Promise<void>;
  isSaving?: boolean;
  saveAnnouncement?: string;
  previewUrl: string;
  activeLine?: number;
}

export function IdeEditorPane({
  openFiles,
  activeFilePath,
  onSelectFileTab,
  onCloseFileTab,
  onChangeFileContent,
  onSaveFile,
  isSaving = false,
  saveAnnouncement = "",
  previewUrl,
}: IdeEditorPaneProps) {
  const [stageMode, setStageMode] = React.useState<"code" | "web-preview" | "jsx-preview">("code");
  const activeFile = openFiles.find((f) => f.path === activeFilePath) || null;
  const isDirty = Boolean(activeFile && activeFile.content !== activeFile.savedContent);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      if (activeFile) {
        void onSaveFile(activeFile.path);
      }
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
      {/* Stage Mode + File Tabs Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-card px-2 py-1">
        <div
          role="tablist"
          aria-label="Open files"
          className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto"
        >
          {openFiles.map((file) => {
            const fileName = file.path.split("/").pop() || file.path;
            const fileDirty = file.content !== file.savedContent;
            const isActive = stageMode === "code" && file.path === activeFilePath;

            return (
              <div
                key={file.path}
                className={cn(
                  "group flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition-colors",
                  isActive
                    ? "border-primary/40 bg-background font-medium text-foreground"
                    : "border-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                )}
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => {
                    setStageMode("code");
                    onSelectFileTab(file.path);
                  }}
                  className="flex items-center gap-1.5 font-mono text-[11px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span>{fileName}</span>
                  {fileDirty && (
                    <span
                      aria-label="Unsaved changes"
                      className="size-1.5 rounded-full bg-amber-500"
                    />
                  )}
                </button>
                <button
                  type="button"
                  aria-label={`Close ${fileName}`}
                  onClick={() => onCloseFileTab(file.path)}
                  className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <XIcon className="size-3" aria-hidden="true" />
                </button>
              </div>
            );
          })}
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {activeFile && stageMode === "code" && (
            <Button
              type="button"
              size="sm"
              variant={isDirty ? "default" : "outline"}
              disabled={isSaving || !isDirty}
              onClick={() => void onSaveFile(activeFile.path)}
              className="h-7 gap-1 px-2.5 text-xs"
            >
              <SaveIcon className="size-3" aria-hidden="true" />
              <span>{isSaving ? "Saving..." : "Save"}</span>
            </Button>
          )}

          <Tabs
            value={stageMode}
            onValueChange={(v) => setStageMode(v as "code" | "web-preview" | "jsx-preview")}
          >
            <TabsList className="h-7">
              <TabsTrigger value="code" className="gap-1 px-2 text-[11px]">
                <Code2Icon className="size-3" aria-hidden="true" />
                <span>Code</span>
              </TabsTrigger>
              <TabsTrigger value="web-preview" className="gap-1 px-2 text-[11px]">
                <GlobeIcon className="size-3" aria-hidden="true" />
                <span>Web Preview</span>
              </TabsTrigger>
              <TabsTrigger value="jsx-preview" className="gap-1 px-2 text-[11px]">
                <EyeIcon className="size-3" aria-hidden="true" />
                <span>JSX</span>
              </TabsTrigger>
            </TabsList>
            <TabsContent value="code" className="hidden" />
            <TabsContent value="web-preview" className="hidden" />
            <TabsContent value="jsx-preview" className="hidden" />
          </Tabs>
        </div>
      </div>

      <div aria-live="polite" className="sr-only">
        {saveAnnouncement}
      </div>

      {/* Main Stage Body */}
      <div className="min-h-0 flex-1 overflow-auto">
        {stageMode === "web-preview" ? (
          <div className="h-full p-3">
            <WebPreview url={previewUrl} className="h-full" />
          </div>
        ) : stageMode === "jsx-preview" ? (
          <div className="p-3">
            <JSXPreview
              title={activeFile?.path || "JSX Preview"}
              jsx={activeFile?.content || "<div>Select a JSX/TSX file to preview</div>"}
            />
          </div>
        ) : activeFile ? (
          <div className="flex h-full flex-col">
            <div className="border-b border-border/60 bg-muted/20 px-3 py-1 font-mono text-[11px] text-muted-foreground">
              {activeFile.path}
            </div>
            <textarea
              aria-label={`Code editor for ${activeFile.path}`}
              value={activeFile.content}
              onChange={(e) => onChangeFileContent(activeFile.path, e.target.value)}
              onKeyDown={handleKeyDown}
              spellCheck={false}
              className="min-h-0 flex-1 resize-none bg-background p-4 font-mono text-xs leading-relaxed text-foreground focus:outline-none"
            />
          </div>
        ) : (
          <div className="flex h-full items-center justify-center p-6 text-xs text-muted-foreground">
            Select a file from the Explorer to view or edit it.
          </div>
        )}
      </div>
    </div>
  );
}
