"use client";

import * as React from "react";
import { CompassIcon, GlobeIcon, SearchIcon } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";

export function UrlInputCard({
  rawUrls,
  onRawUrlsChange,
  enableDiscovery,
  onEnableDiscoveryChange,
  onDiscover,
  isDiscovering = false,
  maxPages,
  onMaxPagesChange,
  ignoreRobots,
  onIgnoreRobotsChange,
  disabled = false,
}: {
  rawUrls: string;
  onRawUrlsChange: (val: string) => void;
  enableDiscovery: boolean;
  onEnableDiscoveryChange: (enabled: boolean) => void;
  onDiscover?: () => void;
  isDiscovering?: boolean;
  maxPages: number;
  onMaxPagesChange: (val: number) => void;
  ignoreRobots: boolean;
  onIgnoreRobotsChange: (val: boolean) => void;
  disabled?: boolean;
}) {
  const urlCount = rawUrls
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean).length;

  return (
    <Card className="border-border/60">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <GlobeIcon className="h-4 w-4 text-primary" />
          <CardTitle className="text-base">2. Target Webpage URLs</CardTitle>
        </div>
        <CardDescription>
          Provide website URLs to crawl directly, or enable automated site-wide discovery via sitemaps.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Discovery Mode Toggle */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg border border-border/50 bg-muted/30">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <CompassIcon className="h-4 w-4 text-primary" />
              <Label htmlFor="disc-switch" className="text-xs font-semibold cursor-pointer">
                Automated Site Discovery (Sitemap & Depth Crawling)
              </Label>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Automatically discovers all available URLs across the domain via robots.txt, sitemaps, and link traversal.
            </p>
          </div>
          <Switch
            id="disc-switch"
            checked={enableDiscovery}
            onCheckedChange={onEnableDiscoveryChange}
            disabled={disabled}
          />
        </div>

        {/* URLs Textarea */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="urls-input" className="text-xs font-medium">
              {enableDiscovery ? "Root Website URL(s) to Scan" : "Explicit Page URLs (one per line)"}
            </Label>
            <span className="text-[11px] text-muted-foreground font-mono">
              {urlCount} {urlCount === 1 ? "URL" : "URLs"} entered
            </span>
          </div>
          <Textarea
            id="urls-input"
            rows={enableDiscovery ? 2 : 4}
            placeholder={
              enableDiscovery
                ? "https://example.com"
                : "https://example.com/page-1\nhttps://example.com/page-2"
            }
            value={rawUrls}
            onChange={(e) => onRawUrlsChange(e.target.value)}
            disabled={disabled}
            className="font-mono text-xs"
          />
        </div>

        {/* Discovery Action Button */}
        {enableDiscovery && onDiscover && (
          <div className="flex flex-col sm:flex-row items-center gap-3 pt-1">
            <Button
              type="button"
              variant="secondary"
              className="w-full sm:w-auto h-8 text-xs gap-1.5"
              onClick={onDiscover}
              disabled={disabled || isDiscovering || urlCount === 0}
            >
              <SearchIcon className="h-3.5 w-3.5" />
              {isDiscovering ? "Scanning Sitemap..." : "Discover Site URLs"}
            </Button>
            <p className="text-[11px] text-muted-foreground">
              Scans sitemaps and links. You can review and filter the URL list before crawling.
            </p>
          </div>
        )}

        {/* Advanced / Scope Settings */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-border/40">
          <div className="space-y-1.5">
            <Label htmlFor="maxPagesInput" className="text-xs font-medium">
              Maximum Pages to Crawl
            </Label>
            <Input
              id="maxPagesInput"
              type="number"
              min={1}
              max={1000}
              value={maxPages}
              onChange={(e) => onMaxPagesChange(Math.min(1000, Math.max(1, parseInt(e.target.value) || 1)))}
              disabled={disabled}
              className="h-8 text-xs"
            />
            <p className="text-[11px] text-muted-foreground">
              Default 100 pages. Hard cap is 1000 pages per project.
            </p>
          </div>

          <div className="flex flex-col justify-center space-y-1.5">
            <div className="flex items-center justify-between pt-1">
              <Label htmlFor="ignoreRobots" className="text-xs font-medium cursor-pointer">
                Ignore robots.txt
              </Label>
              <Switch
                id="ignoreRobots"
                checked={ignoreRobots}
                onCheckedChange={onIgnoreRobotsChange}
                disabled={disabled}
              />
            </div>
            <p className="text-[11px] text-muted-foreground">
              By default, disallowed URLs in robots.txt are excluded.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
