"use client";

import * as React from "react";
import {
  CheckIcon,
  Code2Icon,
  CopyIcon,
  DownloadIcon,
  FileTextIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ArtifactProps {
  title: string;
  description?: string;
  filePath?: string;
  content: string;
  language?: string;
  onOpenInIde?: (filePath: string) => void;
  className?: string;
}

export function Artifact({
  title,
  description,
  filePath,
  content,
  language,
  onOpenInIde,
  className,
}: ArtifactProps) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // ignore
    }
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = (filePath || title).split("/").pop() || "artifact.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card text-card-foreground",
        className
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/40 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <FileTextIcon className="size-4 shrink-0 text-primary" aria-hidden="true" />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate text-xs font-semibold">{title}</span>
              {language && (
                <Badge variant="outline" className="font-mono text-[10px]">
                  {language}
                </Badge>
              )}
            </div>
            {description && (
              <p className="truncate text-[11px] text-muted-foreground">{description}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1">
          {filePath && onOpenInIde && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenInIde(filePath)}
              className="h-7 gap-1 px-2 text-xs"
            >
              <Code2Icon className="size-3" aria-hidden="true" />
              <span>Open in IDE</span>
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => void handleCopy()}
            aria-label={`Copy ${title}`}
            className="size-7"
          >
            {copied ? (
              <CheckIcon className="size-3.5 text-emerald-500" aria-hidden="true" />
            ) : (
              <CopyIcon className="size-3.5" aria-hidden="true" />
            )}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={handleDownload}
            aria-label={`Download ${title}`}
            className="size-7"
          >
            <DownloadIcon className="size-3.5" aria-hidden="true" />
          </Button>
        </div>
      </div>

      <pre className="max-h-64 overflow-auto p-3 font-mono text-xs leading-relaxed text-foreground">
        <code>{content}</code>
      </pre>
    </div>
  );
}
