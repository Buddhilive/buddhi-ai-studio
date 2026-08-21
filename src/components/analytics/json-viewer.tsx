"use client";

import { useMemo, useState } from "react";

import {
  CodeBlock,
  CodeBlockCopyButton,
  CodeBlockHeader,
  CodeBlockActions,
  CodeBlockTitle,
} from "@/components/ai-elements/code-block";
import { Button } from "@/components/ui/button";

const MAX_CHARS = 20_000;

export function JsonViewer({ data, title = "JSON" }: { data: unknown; title?: string }) {
  const [expanded, setExpanded] = useState(false);

  const full = useMemo(() => JSON.stringify(data, null, 2), [data]);
  const isTruncated = full.length > MAX_CHARS && !expanded;
  const code = isTruncated ? full.slice(0, MAX_CHARS) : full;

  return (
    <CodeBlock code={code} language="json" showLineNumbers>
      <CodeBlockHeader>
        <CodeBlockTitle>{title}</CodeBlockTitle>
        <CodeBlockActions>
          {full.length > MAX_CHARS && (
            <Button variant="ghost" size="sm" onClick={() => setExpanded((v) => !v)}>
              {expanded ? "Show less" : "Show more"}
            </Button>
          )}
          <CodeBlockCopyButton />
        </CodeBlockActions>
      </CodeBlockHeader>
    </CodeBlock>
  );
}
