"use client";

import * as React from "react";
import { CheckIcon, ExternalLinkIcon, FilterIcon, ShieldAlertIcon } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DiscoveredUrl } from "@/lib/site-crawler/types";
import { matchesGlob } from "@/lib/site-crawler/glob";

export function DiscoveryTable({
  discoveredUrls,
  selectedUrls,
  onSelectionChange,
  maxPages,
}: {
  discoveredUrls: DiscoveredUrl[];
  selectedUrls: Set<string>;
  onSelectionChange: (updated: Set<string>) => void;
  maxPages: number;
}) {
  const [includeText, setIncludeText] = React.useState("");
  const [excludeText, setExcludeText] = React.useState("");

  const includePatterns = React.useMemo(
    () => includeText.split(",").map((s) => s.trim()).filter(Boolean),
    [includeText]
  );
  const excludePatterns = React.useMemo(
    () => excludeText.split(",").map((s) => s.trim()).filter(Boolean),
    [excludeText]
  );

  const filteredUrls = React.useMemo(() => {
    return discoveredUrls.filter((item) => {
      let path = item.url;
      try {
        path = new URL(item.url).pathname;
      } catch {
        // fallback
      }

      if (excludePatterns.length > 0) {
        if (excludePatterns.some((p) => matchesGlob(path, p) || matchesGlob(item.url, p))) {
          return false;
        }
      }

      if (includePatterns.length > 0) {
        if (!includePatterns.some((p) => matchesGlob(path, p) || matchesGlob(item.url, p))) {
          return false;
        }
      }

      return true;
    });
  }, [discoveredUrls, includePatterns, excludePatterns]);

  const handleToggleSelectAll = (checked: boolean) => {
    const updated = new Set(selectedUrls);
    for (const item of filteredUrls) {
      if (checked) {
        updated.add(item.url);
      } else {
        updated.delete(item.url);
      }
    }
    onSelectionChange(updated);
  };

  const handleToggleItem = (url: string, checked: boolean) => {
    const updated = new Set(selectedUrls);
    if (checked) {
      updated.add(url);
    } else {
      updated.delete(url);
    }
    onSelectionChange(updated);
  };

  const selectedCount = selectedUrls.size;
  const isCapExceeded = selectedCount > maxPages;

  return (
    <Card className="border-border/60">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <CardTitle className="text-base">Discovered Site URLs</CardTitle>
              <Badge variant="outline" className="text-xs font-mono">
                {selectedCount} / {discoveredUrls.length} selected
              </Badge>
              {isCapExceeded && (
                <Badge variant="destructive" className="text-[11px] gap-1">
                  Exceeds cap ({maxPages} max will be crawled)
                </Badge>
              )}
            </div>
            <CardDescription>
              Review and select the target URLs before launching the extraction job.
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="xs"
              className="text-xs h-7"
              onClick={() => handleToggleSelectAll(true)}
            >
              Select All
            </Button>
            <Button
              variant="outline"
              size="xs"
              className="text-xs h-7"
              onClick={() => handleToggleSelectAll(false)}
            >
              Deselect All
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Filters */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 rounded-lg border border-border/50 bg-muted/20">
          <div className="space-y-1">
            <Label htmlFor="inc-pat" className="text-[11px] font-medium flex items-center gap-1.5">
              <FilterIcon className="h-3 w-3 text-muted-foreground" />
              Include Patterns (comma-separated globs)
            </Label>
            <Input
              id="inc-pat"
              placeholder="e.g. /products/*, /docs/*"
              value={includeText}
              onChange={(e) => setIncludeText(e.target.value)}
              className="h-7 text-xs"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="exc-pat" className="text-[11px] font-medium flex items-center gap-1.5">
              <FilterIcon className="h-3 w-3 text-muted-foreground" />
              Exclude Patterns (comma-separated globs)
            </Label>
            <Input
              id="exc-pat"
              placeholder="e.g. /cart/*, /login, *.pdf"
              value={excludeText}
              onChange={(e) => setExcludeText(e.target.value)}
              className="h-7 text-xs"
            />
          </div>
        </div>

        {/* URLs Table */}
        <div className="rounded-md border border-border/60 overflow-hidden">
          <div className="overflow-x-auto max-h-[360px]">
            <Table>
              <TableHeader className="bg-muted/50 sticky top-0 z-10 backdrop-blur-sm">
                <TableRow>
                  <TableHead className="w-12 text-center">
                    <Checkbox
                      checked={
                        filteredUrls.length > 0 &&
                        filteredUrls.every((u) => selectedUrls.has(u.url))
                      }
                      onCheckedChange={(c) => handleToggleSelectAll(Boolean(c))}
                    />
                  </TableHead>
                  <TableHead className="text-xs font-semibold">Webpage URL</TableHead>
                  <TableHead className="text-xs font-semibold w-24">Source</TableHead>
                  <TableHead className="text-xs font-semibold w-24">Robots</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUrls.map((item) => {
                  const isChecked = selectedUrls.has(item.url);
                  return (
                    <TableRow key={item.url} className="hover:bg-muted/30">
                      <TableCell className="text-center py-2">
                        <Checkbox
                          checked={isChecked}
                          onCheckedChange={(c) => handleToggleItem(item.url, Boolean(c))}
                        />
                      </TableCell>
                      <TableCell className="py-2 text-xs font-mono max-w-md truncate">
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-foreground hover:text-primary transition-colors"
                        >
                          <span className="truncate">{item.url}</span>
                          <ExternalLinkIcon className="h-3 w-3 shrink-0 text-muted-foreground" />
                        </a>
                      </TableCell>
                      <TableCell className="py-2">
                        <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-mono">
                          {item.source}
                        </Badge>
                      </TableCell>
                      <TableCell className="py-2">
                        {item.allowed ? (
                          <Badge variant="outline" className="text-[10px] py-0 px-1.5 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                            Allowed
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-[10px] py-0 px-1.5 text-amber-600 dark:text-amber-400 border-amber-500/30 gap-1">
                            <ShieldAlertIcon className="h-2.5 w-2.5" />
                            Disallow
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
