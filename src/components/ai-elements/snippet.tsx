"use client";

import * as React from "react";
import { CheckIcon, CopyIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface SnippetProps {
  code: string;
  label?: string;
  className?: string;
}

export function Snippet({ code, label, className }: SnippetProps) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  };

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-2 rounded-md border border-border bg-muted/40 px-3 py-1.5 font-mono text-xs",
        className
      )}
    >
      <div className="min-w-0 flex-1 truncate">
        {label && (
          <span className="mr-2 text-[11px] font-semibold text-muted-foreground">
            {label}
          </span>
        )}
        <code className="text-foreground">{code}</code>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={copied ? "Copied snippet" : "Copy snippet"}
        onClick={() => void handleCopy()}
        className="size-6 shrink-0"
      >
        {copied ? (
          <CheckIcon className="size-3.5 text-emerald-500" aria-hidden="true" />
        ) : (
          <CopyIcon className="size-3.5" aria-hidden="true" />
        )}
      </Button>
      <span aria-live="polite" className="sr-only">
        {copied ? "Copied to clipboard" : ""}
      </span>
    </div>
  );
}
