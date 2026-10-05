"use client";

import * as React from "react";
import { GlobeIcon, SlidersHorizontalIcon, Loader2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

export interface CrawlerConfig {
  url: string;
  cssSelector: string;
  onlyMainContent: boolean;
  waitFor: string;
  bypassCache: boolean;
  timeoutS: number;
}

interface CrawlerFormProps {
  onCrawl: (config: CrawlerConfig) => void;
  isLoading: boolean;
}

export function CrawlerForm({ onCrawl, isLoading }: CrawlerFormProps) {
  const [url, setUrl] = React.useState("https://example.com");
  const [cssSelector, setCssSelector] = React.useState("");
  const [onlyMainContent, setOnlyMainContent] = React.useState(true);
  const [waitFor, setWaitFor] = React.useState("");
  const [bypassCache, setBypassCache] = React.useState(false);
  const [timeoutS, setTimeoutS] = React.useState(60);
  const [showAdvanced, setShowAdvanced] = React.useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim() || isLoading) return;
    onCrawl({
      url: url.trim(),
      cssSelector: cssSelector.trim(),
      onlyMainContent,
      waitFor: waitFor.trim(),
      bypassCache,
      timeoutS,
    });
  };

  return (
    <Card className="border border-border/60 bg-card shadow-sm">
      <CardContent className="p-4 sm:p-6 space-y-4">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <GlobeIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Enter URL to crawl (e.g. https://docs.crawl4ai.com)"
                className="pl-9 text-sm"
                required
                disabled={isLoading}
              />
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="gap-1.5 text-xs text-muted-foreground h-9"
              >
                <SlidersHorizontalIcon className="h-3.5 w-3.5" />
                Options
              </Button>
              <Button type="submit" disabled={isLoading || !url.trim()} className="h-9 px-4">
                {isLoading ? (
                  <>
                    <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />
                    Crawling...
                  </>
                ) : (
                  "Crawl URL"
                )}
              </Button>
            </div>
          </div>

          {showAdvanced && (
            <div className="pt-3 border-t border-border/50 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div className="space-y-1">
                <label className="font-medium text-foreground">CSS Selector (optional)</label>
                <Input
                  value={cssSelector}
                  onChange={(e) => setCssSelector(e.target.value)}
                  placeholder="e.g. article, .main-content"
                  className="h-8 text-xs"
                  disabled={isLoading}
                />
              </div>

              <div className="space-y-1">
                <label className="font-medium text-foreground">Wait Before Extraction</label>
                <Input
                  value={waitFor}
                  onChange={(e) => setWaitFor(e.target.value)}
                  placeholder="e.g. 2 (seconds) or selector"
                  className="h-8 text-xs"
                  disabled={isLoading}
                />
              </div>

              <div className="space-y-1">
                <label className="font-medium text-foreground">Timeout (seconds)</label>
                <Input
                  type="number"
                  min={5}
                  max={300}
                  value={timeoutS}
                  onChange={(e) => setTimeoutS(Number(e.target.value) || 60)}
                  className="h-8 text-xs"
                  disabled={isLoading}
                />
              </div>

              <div className="flex flex-col justify-end space-y-2 pt-1">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={onlyMainContent}
                    onChange={(e) => setOnlyMainContent(e.target.checked)}
                    disabled={isLoading}
                    className="rounded border-border text-primary focus:ring-primary"
                  />
                  <span className="text-foreground">Filter main content only</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={bypassCache}
                    onChange={(e) => setBypassCache(e.target.checked)}
                    disabled={isLoading}
                    className="rounded border-border text-primary focus:ring-primary"
                  />
                  <span className="text-foreground">Bypass crawler cache</span>
                </label>
              </div>
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
