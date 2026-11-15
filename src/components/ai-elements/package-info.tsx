"use client";

import * as React from "react";
import { PackageIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface PackageInfoProps {
  name: string;
  version?: string;
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
  scripts?: Record<string, string>;
  className?: string;
}

export function PackageInfo({
  name,
  version,
  dependencies = {},
  devDependencies = {},
  scripts = {},
  className,
}: PackageInfoProps) {
  const deps = Object.entries(dependencies);
  const devDeps = Object.entries(devDependencies);
  const scriptEntries = Object.entries(scripts);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card text-xs",
        className
      )}
    >
      <div className="flex items-center justify-between border-b border-border bg-muted/40 px-3 py-2">
        <div className="flex items-center gap-2">
          <PackageIcon className="size-3.5 text-primary" aria-hidden="true" />
          <span className="font-semibold">{name}</span>
        </div>
        {version && (
          <Badge variant="outline" className="font-mono text-[10px] tabular-nums">
            v{version}
          </Badge>
        )}
      </div>

      <div className="space-y-3 p-3">
        {deps.length > 0 && (
          <div>
            <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Dependencies ({deps.length})
            </h4>
            <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
              {deps.map(([pkg, ver]) => (
                <div
                  key={pkg}
                  className="flex items-center justify-between rounded border border-border/60 px-2 py-1 font-mono text-[11px]"
                >
                  <span className="truncate">{pkg}</span>
                  <span className="ml-2 shrink-0 text-muted-foreground tabular-nums">{ver}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {devDeps.length > 0 && (
          <div>
            <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Dev Dependencies ({devDeps.length})
            </h4>
            <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
              {devDeps.map(([pkg, ver]) => (
                <div
                  key={pkg}
                  className="flex items-center justify-between rounded border border-border/60 px-2 py-1 font-mono text-[11px]"
                >
                  <span className="truncate">{pkg}</span>
                  <span className="ml-2 shrink-0 text-muted-foreground tabular-nums">{ver}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {scriptEntries.length > 0 && (
          <div>
            <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Scripts
            </h4>
            <div className="space-y-1">
              {scriptEntries.map(([scriptName, cmd]) => (
                <div
                  key={scriptName}
                  className="flex items-center justify-between gap-2 rounded bg-muted/40 px-2 py-1 font-mono text-[11px]"
                >
                  <span className="font-semibold text-primary">{scriptName}</span>
                  <span className="truncate text-muted-foreground">{cmd}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
