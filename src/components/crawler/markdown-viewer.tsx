"use client";

import * as React from "react";
import { CheckIcon, CopyIcon, FileTextIcon, CodeIcon, FileCodeIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface MarkdownViewerProps {
  markdown: string;
  html?: string | null;
  title?: string;
  url?: string;
}

export function MarkdownViewer({ markdown, html, title, url }: MarkdownViewerProps) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!markdown && !html) {
    return (
      <Card className="border border-dashed border-border/70 p-8 text-center text-muted-foreground bg-muted/20">
        <FileTextIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No crawl output yet. Enter a URL above and click &quot;Crawl URL&quot; to begin.</p>
      </Card>
    );
  }

  return (
    <Card className="border border-border/60 shadow-sm overflow-hidden flex flex-col h-[600px]">
      <Tabs defaultValue="rendered" className="flex flex-col h-full">
        <CardHeader className="py-2.5 px-4 border-b border-border/50 flex flex-row items-center justify-between space-y-0">
          <div className="flex items-center gap-2">
            <TabsList className="h-8">
              <TabsTrigger value="rendered" className="text-xs h-7 gap-1.5">
                <FileTextIcon className="h-3.5 w-3.5" />
                Rendered
              </TabsTrigger>
              <TabsTrigger value="raw" className="text-xs h-7 gap-1.5">
                <CodeIcon className="h-3.5 w-3.5" />
                Raw Markdown
              </TabsTrigger>
              {html && (
                <TabsTrigger value="html" className="text-xs h-7 gap-1.5">
                  <FileCodeIcon className="h-3.5 w-3.5" />
                  HTML
                </TabsTrigger>
              )}
            </TabsList>
            {title && (
              <span className="text-xs text-muted-foreground truncate max-w-xs hidden sm:inline" title={title}>
                {title}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleCopy(markdown)}
              className="h-7 text-xs gap-1.5"
            >
              {copied ? (
                <>
                  <CheckIcon className="h-3.5 w-3.5 text-green-500" />
                  Copied
                </>
              ) : (
                <>
                  <CopyIcon className="h-3.5 w-3.5" />
                  Copy Markdown
                </>
              )}
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-0 flex-1 overflow-hidden relative">
          <TabsContent value="rendered" className="h-full m-0 p-4 overflow-y-auto font-sans leading-relaxed text-sm">
            <div className="prose dark:prose-invert max-w-none space-y-4 whitespace-pre-wrap font-sans">
              {markdown}
            </div>
          </TabsContent>

          <TabsContent value="raw" className="h-full m-0 p-4 overflow-y-auto bg-muted/30">
            <pre className="font-mono text-xs text-foreground whitespace-pre-wrap break-all leading-normal">
              {markdown}
            </pre>
          </TabsContent>

          {html && (
            <TabsContent value="html" className="h-full m-0 p-4 overflow-y-auto bg-muted/30">
              <pre className="font-mono text-xs text-muted-foreground whitespace-pre-wrap break-all leading-normal">
                {html}
              </pre>
            </TabsContent>
          )}
        </CardContent>
      </Tabs>
    </Card>
  );
}
