"use client";

import * as React from "react";
import { GlobeIcon, ShieldCheckIcon, AlertTriangleIcon, SparklesIcon } from "lucide-react";
import { CrawlerForm, CrawlerConfig } from "@/components/crawler/crawler-form";
import { MarkdownViewer } from "@/components/crawler/markdown-viewer";
import { MetadataCard, CrawlResultData } from "@/components/crawler/metadata-card";
import { Badge } from "@/components/ui/badge";

export default function CrawlerPage() {
  const [isLoading, setIsLoading] = React.useState(false);
  const [result, setResult] = React.useState<CrawlResultData | null>(null);
  const [healthStatus, setHealthStatus] = React.useState<{ connected: boolean; version?: string } | null>(null);

  const fetchHealth = React.useCallback(async () => {
    try {
      const res = await fetch("/api/crawl");
      if (res.ok) {
        const data = await res.json();
        setHealthStatus({ connected: data.status === "healthy", version: data.version });
      } else {
        setHealthStatus({ connected: false });
      }
    } catch {
      setHealthStatus({ connected: false });
    }
  }, []);

  React.useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  const handleCrawl = async (config: CrawlerConfig) => {
    setIsLoading(true);
    setResult(null);

    try {
      const payload: Record<string, unknown> = {
        url: config.url,
        only_main_content: config.onlyMainContent,
        bypass_cache: config.bypassCache,
        timeout_s: config.timeoutS,
      };

      if (config.cssSelector) {
        payload.css_selector = config.cssSelector;
      }
      if (config.waitFor) {
        payload.wait_for = config.waitFor;
      }

      const res = await fetch("/api/crawl", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        setResult({
          url: config.url,
          status: "failed",
          title: "",
          markdown: "",
          status_code: res.status,
          links_count: 0,
          media_count: 0,
          execution_duration_ms: 0,
          error: data.detail || data.error || `HTTP ${res.status}: Failed to crawl webpage`,
        });
      } else {
        setResult(data);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setResult({
        url: config.url,
        status: "failed",
        title: "",
        markdown: "",
        status_code: 500,
        links_count: 0,
        media_count: 0,
        execution_duration_ms: 0,
        error: message,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 sm:p-6 max-w-7xl mx-auto w-full">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/40 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <GlobeIcon className="h-5 w-5" />
            </div>
            <h1 className="text-xl font-bold tracking-tight">Crawl4AI Web Crawler</h1>
            <Badge variant="outline" className="text-xs font-mono gap-1 ml-1 border-primary/30 text-primary">
              <SparklesIcon className="h-3 w-3" />
              LLM Extraction
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Extract clean, LLM-ready markdown, structured text, and media using self-hosted headless browser crawling.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {healthStatus && (
            <Badge
              variant="outline"
              className={`text-xs gap-1.5 py-1 px-2.5 ${
                healthStatus.connected
                  ? "border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"
                  : "border-amber-500/30 text-amber-600 dark:text-amber-400 bg-amber-500/10"
              }`}
            >
              {healthStatus.connected ? (
                <>
                  <ShieldCheckIcon className="h-3.5 w-3.5" />
                  Service Connected {healthStatus.version ? `(v${healthStatus.version})` : ""}
                </>
              ) : (
                <>
                  <AlertTriangleIcon className="h-3.5 w-3.5" />
                  Container Offline
                </>
              )}
            </Badge>
          )}
        </div>
      </div>

      {/* Crawler Form */}
      <CrawlerForm onCrawl={handleCrawl} isLoading={isLoading} />

      {/* Metadata Overview */}
      {result && <MetadataCard result={result} />}

      {/* Markdown / HTML Viewer */}
      <MarkdownViewer
        markdown={result?.markdown || ""}
        html={result?.html}
        title={result?.title}
        url={result?.url}
      />
    </div>
  );
}
