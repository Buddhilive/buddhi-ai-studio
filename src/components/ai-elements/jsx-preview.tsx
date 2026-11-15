"use client";

import * as React from "react";
import JsxParser from "react-jsx-parser";
import { Code2Icon, EyeIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

class JsxErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: string | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(err: Error) {
    return { error: err.message };
  }

  render() {
    if (this.state.error) {
      return (
        <div role="alert" className="rounded border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
          Preview Error: {this.state.error}
        </div>
      );
    }
    return this.props.children;
  }
}

export interface JSXPreviewProps {
  jsx: string;
  title?: string;
  className?: string;
}

export function JSXPreview({
  jsx,
  title = "JSX Preview",
  className,
}: JSXPreviewProps) {
  const [mode, setMode] = React.useState<"preview" | "code">("preview");

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card text-xs",
        className
      )}
    >
      <div className="flex items-center justify-between border-b border-border bg-muted/40 px-3 py-1.5">
        <span className="font-semibold">{title}</span>
        <div role="group" aria-label="JSX view mode" className="inline-flex gap-1">
          <Button
            type="button"
            variant={mode === "preview" ? "secondary" : "ghost"}
            size="sm"
            aria-pressed={mode === "preview"}
            onClick={() => setMode("preview")}
            className="h-6 gap-1 px-2 text-[11px]"
          >
            <EyeIcon className="size-3" aria-hidden="true" />
            <span>Preview</span>
          </Button>
          <Button
            type="button"
            variant={mode === "code" ? "secondary" : "ghost"}
            size="sm"
            aria-pressed={mode === "code"}
            onClick={() => setMode("code")}
            className="h-6 gap-1 px-2 text-[11px]"
          >
            <Code2Icon className="size-3" aria-hidden="true" />
            <span>Code</span>
          </Button>
        </div>
      </div>

      {mode === "preview" ? (
        <div className="p-4">
          <JsxErrorBoundary key={jsx}>
            <JsxParser
              jsx={jsx}
              bindings={{}}
              blacklistedTags={["script", "iframe", "object", "embed", "style"]}
              blacklistedAttrs={[/^on/i, "dangerouslySetInnerHTML"]}
              renderInWrapper={false}
            />
          </JsxErrorBoundary>
        </div>
      ) : (
        <pre className="max-h-64 overflow-auto p-3 font-mono text-[11px]">
          <code>{jsx}</code>
        </pre>
      )}
    </div>
  );
}
