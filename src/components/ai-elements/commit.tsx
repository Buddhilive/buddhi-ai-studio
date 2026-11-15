"use client";

import * as React from "react";
import { GitBranchIcon, GitCommitHorizontalIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface CommitFileChange {
  path: string;
  status?: "added" | "modified" | "deleted";
  additions?: number;
  deletions?: number;
}

export interface CommitProps {
  hash: string;
  message: string;
  author?: string;
  branch?: string;
  timestamp?: string;
  files?: CommitFileChange[];
  className?: string;
}

export function Commit({
  hash,
  message,
  author = "BuddhiAI",
  branch,
  timestamp,
  files = [],
  className,
}: CommitProps) {
  const shortHash = hash.slice(0, 7);

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card p-3 text-xs text-card-foreground",
        className
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <GitCommitHorizontalIcon className="size-4 text-primary" aria-hidden="true" />
          <span className="font-semibold text-foreground">{message}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {branch && (
            <Badge variant="outline" className="gap-1 font-mono text-[10px]">
              <GitBranchIcon className="size-3" aria-hidden="true" />
              <span>{branch}</span>
            </Badge>
          )}
          <Badge variant="secondary" className="font-mono text-[10px] tabular-nums">
            {shortHash}
          </Badge>
        </div>
      </div>

      <div className="mt-1.5 flex items-center gap-2 text-[11px] text-muted-foreground">
        <span>{author}</span>
        {timestamp && (
          <>
            <span aria-hidden="true">·</span>
            <span className="font-mono tabular-nums">{timestamp}</span>
          </>
        )}
      </div>

      {files.length > 0 && (
        <ul className="mt-2.5 space-y-1 border-t border-border/60 pt-2">
          {files.map((file) => (
            <li
              key={file.path}
              className="flex items-center justify-between gap-2 font-mono text-[11px]"
            >
              <span className="truncate text-foreground">{file.path}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {typeof file.additions === "number" && (
                  <span className="text-emerald-600 dark:text-emerald-400">+{file.additions} </span>
                )}
                {typeof file.deletions === "number" && (
                  <span className="text-rose-600 dark:text-rose-400">-{file.deletions}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
