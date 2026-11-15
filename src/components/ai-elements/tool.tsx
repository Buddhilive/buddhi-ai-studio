"use client";

import * as React from "react";
import {
  ChevronRightIcon,
  WrenchIcon,
  CheckCircle2Icon,
  AlertCircleIcon,
  Loader2Icon,
  SearchIcon,
  GlobeIcon,
  DatabaseIcon,
  LayersIcon,
  ShieldCheckIcon,
  BookOpenIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Badge } from "@/components/ui/badge";

export interface ToolCardProps {
  toolName: string;
  toolCallId?: string;
  argumentsText?: string | Record<string, unknown>;
  output?: string;
  status?: "pending" | "running" | "completed" | "error";
  exitCode?: number;
  truncated?: boolean;
  className?: string;
}

export function ToolCard({
  toolName,
  toolCallId,
  argumentsText,
  output,
  status = "completed",
  exitCode = 0,
  truncated = false,
  className,
}: ToolCardProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  const formattedArgs = React.useMemo(() => {
    if (!argumentsText) return "";
    if (typeof argumentsText === "string") {
      try {
        return JSON.stringify(JSON.parse(argumentsText), null, 2);
      } catch {
        return argumentsText;
      }
    }
    return JSON.stringify(argumentsText, null, 2);
  }, [argumentsText]);

  const statusBadge = React.useMemo(() => {
    switch (status) {
      case "running":
      case "pending":
        return (
          <Badge variant="outline" className="flex items-center gap-1 text-xs text-amber-500 border-amber-500/30">
            <Loader2Icon className="size-3 animate-spin" aria-hidden="true" />
            <span>Running</span>
          </Badge>
        );
      case "error":
        return (
          <Badge variant="destructive" className="flex items-center gap-1 text-xs">
            <AlertCircleIcon className="size-3" aria-hidden="true" />
            <span>Error ({exitCode})</span>
          </Badge>
        );
      case "completed":
      default:
        return (
          <Badge variant="outline" className="flex items-center gap-1 text-xs text-emerald-500 border-emerald-500/30">
            <CheckCircle2Icon className="size-3" aria-hidden="true" />
            <span>Completed</span>
          </Badge>
        );
    }
  }, [status, exitCode]);

  const categoryMeta = React.useMemo(() => {
    if (toolName === "search_web") {
      return { label: "SearXNG", Icon: SearchIcon };
    }
    if (toolName.startsWith("crawl_")) {
      return { label: "Crawl4AI", Icon: GlobeIcon };
    }
    if (toolName === "provision_postgres_db" || toolName === "query_database" || toolName === "drizzle_kit") {
      return { label: "Database", Icon: DatabaseIcon };
    }
    if (toolName === "nextjs_devtools" || toolName === "shadcn_registry") {
      return { label: "Next.js Stack", Icon: LayersIcon };
    }
    if (toolName === "better_auth_cli") {
      return { label: "BetterAuth", Icon: ShieldCheckIcon };
    }
    if (toolName === "load_skill") {
      return { label: "Skill", Icon: BookOpenIcon };
    }
    return { label: null, Icon: WrenchIcon };
  }, [toolName]);

  const CategoryIcon = categoryMeta.Icon;

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn("my-2 rounded-lg border bg-card text-card-foreground shadow-xs", className)}
    >
      <CollapsibleTrigger
        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-mono hover:bg-muted/50 rounded-lg focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring transition-colors"
      >
        <div className="flex items-center gap-2 overflow-hidden">
          <ChevronRightIcon
            className={cn("size-3.5 shrink-0 transition-transform duration-200", isOpen && "rotate-90")}
            aria-hidden="true"
          />
          <CategoryIcon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
          {categoryMeta.label ? (
            <Badge variant="secondary" className="text-[10px] font-sans px-1.5 py-0">
              {categoryMeta.label}
            </Badge>
          ) : null}
          <span className="font-semibold truncate">{toolName}</span>
          {toolCallId && (
            <span className="text-[10px] text-muted-foreground hidden sm:inline">
              {toolCallId.slice(0, 10)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">{statusBadge}</div>
      </CollapsibleTrigger>
      <CollapsibleContent className="px-3 pb-3 pt-1 border-t text-xs font-mono space-y-2">
        {formattedArgs && (
          <div>
            <div className="text-[11px] font-sans font-medium text-muted-foreground mb-1">Arguments:</div>
            <pre
              tabIndex={0}
              className="p-2 rounded-md bg-muted text-[11px] overflow-x-auto max-h-40 focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
            >
              {formattedArgs}
            </pre>
          </div>
        )}
        {output && (
          <div>
            <div className="flex items-center justify-between text-[11px] font-sans font-medium text-muted-foreground mb-1">
              <span>Output:</span>
              {truncated && <span className="text-[10px] text-amber-500 font-semibold">[Truncated]</span>}
            </div>
            <pre
              tabIndex={0}
              className="p-2 rounded-md bg-muted text-[11px] overflow-x-auto max-h-56 focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
            >
              {output}
            </pre>
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}
