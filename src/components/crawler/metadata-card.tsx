"use client";

import * as React from "react";
import { LinkIcon, ImageIcon, ClockIcon, CheckCircle2Icon, AlertCircleIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export interface CrawlResultData {
  url: string;
  status: "completed" | "failed" | "timeout";
  title: string;
  markdown: string;
  html?: string | null;
  status_code: number;
  links_count: number;
  media_count: number;
  execution_duration_ms: number;
  error?: string | null;
}

interface MetadataCardProps {
  result: CrawlResultData;
}

export function MetadataCard({ result }: MetadataCardProps) {
  const isSuccess = result.status === "completed";

  return (
    <Card className="border border-border/60 bg-card">
      <CardContent className="p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge
              variant={isSuccess ? "default" : "destructive"}
              className="gap-1 text-xs uppercase font-mono"
            >
              {isSuccess ? (
                <CheckCircle2Icon className="h-3 w-3 text-emerald-400" />
              ) : (
                <AlertCircleIcon className="h-3 w-3" />
              )}
              {result.status}
            </Badge>

            <span className="text-xs font-mono text-muted-foreground">
              HTTP {result.status_code}
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs text-muted-foreground font-mono">
            <span className="flex items-center gap-1">
              <ClockIcon className="h-3.5 w-3.5" />
              {result.execution_duration_ms > 1000
                ? `${(result.execution_duration_ms / 1000).toFixed(2)}s`
                : `${result.execution_duration_ms.toFixed(0)}ms`}
            </span>

            <span className="flex items-center gap-1">
              <LinkIcon className="h-3.5 w-3.5" />
              {result.links_count} links
            </span>

            <span className="flex items-center gap-1">
              <ImageIcon className="h-3.5 w-3.5" />
              {result.media_count} media
            </span>
          </div>
        </div>

        {result.title && (
          <div className="text-sm font-medium text-foreground truncate" title={result.title}>
            {result.title}
          </div>
        )}

        {result.error && (
          <div className="p-2.5 rounded bg-destructive/10 border border-destructive/20 text-destructive text-xs">
            {result.error}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
