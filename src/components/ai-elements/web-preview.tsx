"use client";

import * as React from "react";
import {
  GlobeIcon,
  MonitorIcon,
  RefreshCwIcon,
  SmartphoneIcon,
  TabletIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export type PreviewViewport = "desktop" | "tablet" | "mobile";

export interface WebPreviewProps {
  url: string;
  title?: string;
  className?: string;
}

const VIEWPORT_WIDTHS: Record<PreviewViewport, string> = {
  desktop: "100%",
  tablet: "768px",
  mobile: "390px",
};

function sanitizePreviewUrl(raw: string): string | null {
  try {
    if (raw.startsWith("/")) return raw;
    const parsed = new URL(raw);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
    return null;
  } catch {
    return null;
  }
}

export function WebPreview({
  url,
  title = "Web Preview",
  className,
}: WebPreviewProps) {
  const [prevUrl, setPrevUrl] = React.useState(url);
  const [currentUrl, setCurrentUrl] = React.useState(url);
  const [viewport, setViewport] = React.useState<PreviewViewport>("desktop");
  const [reloadNonce, setReloadNonce] = React.useState(0);

  if (url !== prevUrl) {
    setPrevUrl(url);
    setCurrentUrl(url);
  }

  const safeUrl = sanitizePreviewUrl(currentUrl);

  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden rounded-lg border border-border bg-card text-xs",
        className
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/40 px-3 py-1.5">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <GlobeIcon className="size-3.5 shrink-0 text-primary" aria-hidden="true" />
          <Input
            aria-label="Preview URL"
            value={currentUrl}
            onChange={(e) => setCurrentUrl(e.target.value)}
            className="h-7 font-mono text-[11px]"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Reload preview"
            onClick={() => setReloadNonce((n) => n + 1)}
            className="size-7 shrink-0"
          >
            <RefreshCwIcon className="size-3.5" aria-hidden="true" />
          </Button>
        </div>

        <div role="group" aria-label="Viewport size" className="inline-flex items-center gap-0.5">
          <Button
            type="button"
            variant={viewport === "desktop" ? "secondary" : "ghost"}
            size="icon-sm"
            aria-label="Desktop viewport"
            aria-pressed={viewport === "desktop"}
            onClick={() => setViewport("desktop")}
            className="size-7"
          >
            <MonitorIcon className="size-3.5" aria-hidden="true" />
          </Button>
          <Button
            type="button"
            variant={viewport === "tablet" ? "secondary" : "ghost"}
            size="icon-sm"
            aria-label="Tablet viewport"
            aria-pressed={viewport === "tablet"}
            onClick={() => setViewport("tablet")}
            className="size-7"
          >
            <TabletIcon className="size-3.5" aria-hidden="true" />
          </Button>
          <Button
            type="button"
            variant={viewport === "mobile" ? "secondary" : "ghost"}
            size="icon-sm"
            aria-label="Mobile viewport"
            aria-pressed={viewport === "mobile"}
            onClick={() => setViewport("mobile")}
            className="size-7"
          >
            <SmartphoneIcon className="size-3.5" aria-hidden="true" />
          </Button>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center bg-muted/20 p-2">
        {safeUrl ? (
          <iframe
            key={`${safeUrl}-${reloadNonce}`}
            src={safeUrl}
            title={title}
            sandbox="allow-scripts allow-forms allow-popups"
            style={{ width: VIEWPORT_WIDTHS[viewport] }}
            className="h-80 rounded border border-border bg-white transition-all"
          />
        ) : (
          <div role="alert" className="p-6 text-center text-muted-foreground">
            Invalid or unsupported preview URL. Only http/https URLs are permitted.
          </div>
        )}
      </div>
    </div>
  );
}
