"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangleIcon, BotIcon, DatabaseIcon, GlobeIcon, ShieldCheckIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { SiteCrawlerHealth } from "@/lib/site-crawler/types";

export function ServiceStatusBanner({
  health,
}: {
  health: SiteCrawlerHealth | null;
}) {
  if (!health) {
    return null;
  }

  const { crawl4ai, storage, model, ready } = health;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {/* Crawl4AI Badge */}
        <Badge
          variant="outline"
          className={`text-xs gap-1.5 py-1 px-2.5 ${
            crawl4ai
              ? "border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"
              : "border-amber-500/30 text-amber-600 dark:text-amber-400 bg-amber-500/10"
          }`}
        >
          <GlobeIcon className="h-3.5 w-3.5" />
          Crawl4AI: {crawl4ai ? "Online" : "Offline"}
        </Badge>

        {/* RustFS Storage Badge */}
        <Badge
          variant="outline"
          className={`text-xs gap-1.5 py-1 px-2.5 ${
            storage
              ? "border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"
              : "border-amber-500/30 text-amber-600 dark:text-amber-400 bg-amber-500/10"
          }`}
        >
          <DatabaseIcon className="h-3.5 w-3.5" />
          RustFS: {storage ? "Online" : "Offline"}
        </Badge>

        {/* LLM Model Badge */}
        <Badge
          variant="outline"
          className={`text-xs gap-1.5 py-1 px-2.5 ${
            model.available
              ? "border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"
              : "border-amber-500/30 text-amber-600 dark:text-amber-400 bg-amber-500/10"
          }`}
        >
          <BotIcon className="h-3.5 w-3.5" />
          Model: {model.available ? model.model_id || "Ready" : "Not Downloaded"}
        </Badge>

        {ready && (
          <Badge
            variant="outline"
            className="text-xs gap-1.5 py-1 px-2.5 border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 ml-auto"
          >
            <ShieldCheckIcon className="h-3.5 w-3.5" />
            System Ready
          </Badge>
        )}
      </div>

      {!ready && (
        <div className="flex flex-col gap-2 p-3.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200 text-xs">
          <div className="flex items-center gap-2 font-semibold text-amber-800 dark:text-amber-300">
            <AlertTriangleIcon className="h-4 w-4 text-amber-500 shrink-0" />
            <span>Required Services Unavailable</span>
          </div>
          <div className="space-y-1.5 text-muted-foreground pl-6">
            {!crawl4ai && (
              <p>
                • Crawl4AI is offline. Run:{" "}
                <code className="px-1.5 py-0.5 rounded bg-background/80 border font-mono text-[11px] text-foreground">
                  docker compose -f docker-compose.dev.yml up -d crawl4ai
                </code>
              </p>
            )}
            {!storage && (
              <p>
                • RustFS object storage is offline. Run:{" "}
                <code className="px-1.5 py-0.5 rounded bg-background/80 border font-mono text-[11px] text-foreground">
                  docker compose -f docker-compose.dev.yml up -d rustfs
                </code>
              </p>
            )}
            {!model.available && (
              <p>
                • Default chat model is not downloaded. Visit{" "}
                <Link href="/downloads" className="underline text-primary font-medium hover:opacity-80">
                  Download Model
                </Link>{" "}
                to obtain the local LLM.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
