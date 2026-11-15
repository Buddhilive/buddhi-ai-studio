"use client";

import * as React from "react";
import { RefreshCwIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FileTree, type FileTreeNode } from "@/components/ai-elements/file-tree";
import { PackageInfo } from "@/components/ai-elements/package-info";
import {
  EnvironmentVariables,
  type EnvironmentVariableItem,
} from "@/components/ai-elements/environment-variables";

interface IdeSidebarProps {
  tree: FileTreeNode[];
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
  onRefreshFiles: () => void;
  isRefreshing?: boolean;
  packageData?: {
    name: string;
    version?: string;
    dependencies?: Record<string, string>;
    devDependencies?: Record<string, string>;
    scripts?: Record<string, string>;
  } | null;
  envVars: EnvironmentVariableItem[];
}

export function IdeSidebar({
  tree,
  selectedPath,
  onSelectFile,
  onRefreshFiles,
  isRefreshing = false,
  packageData,
  envVars,
}: IdeSidebarProps) {
  return (
    <aside
      aria-label="IDE Explorer"
      className="flex h-full w-64 shrink-0 flex-col border-r border-border bg-card"
    >
      <Tabs defaultValue="files" className="flex min-h-0 flex-1 flex-col gap-0">
        <div className="flex items-center justify-between border-b border-border px-2 py-1">
          <TabsList variant="line" className="h-7">
            <TabsTrigger value="files" className="px-2 text-xs">
              Files
            </TabsTrigger>
            <TabsTrigger value="packages" className="px-2 text-xs">
              Packages
            </TabsTrigger>
            <TabsTrigger value="env" className="px-2 text-xs">
              Env
            </TabsTrigger>
          </TabsList>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Refresh file tree"
            onClick={onRefreshFiles}
            disabled={isRefreshing}
            className="size-6"
          >
            <RefreshCwIcon
              className={`size-3.5 ${isRefreshing ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
          </Button>
        </div>

        <TabsContent value="files" className="min-h-0 flex-1 overflow-auto p-1">
          <FileTree
            nodes={tree}
            selectedPath={selectedPath}
            onSelectFile={onSelectFile}
          />
        </TabsContent>

        <TabsContent value="packages" className="min-h-0 flex-1 overflow-auto p-2">
          {packageData ? (
            <PackageInfo
              name={packageData.name}
              version={packageData.version}
              dependencies={packageData.dependencies}
              devDependencies={packageData.devDependencies}
              scripts={packageData.scripts}
            />
          ) : (
            <div className="p-2 text-xs text-muted-foreground">
              No package.json detected in workspace.
            </div>
          )}
        </TabsContent>

        <TabsContent value="env" className="min-h-0 flex-1 overflow-auto p-2">
          <EnvironmentVariables variables={envVars} source=".env" />
        </TabsContent>
      </Tabs>
    </aside>
  );
}
