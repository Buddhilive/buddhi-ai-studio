"use client";

import * as React from "react";
import { CheckIcon, CopyIcon, EyeIcon, EyeOffIcon, KeyRoundIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface EnvironmentVariableItem {
  key: string;
  value: string;
  isSecret?: boolean;
}

export interface EnvironmentVariablesProps {
  variables: EnvironmentVariableItem[];
  source?: string;
  className?: string;
}

const SECRET_KEY_RE = /secret|key|token|password|passwd|auth|credential|private|database_url/i;
const CREDENTIALED_URL_RE = /(https?|postgres(?:ql)?|mysql|redis):\/\/[^:]+:[^@]+@/i;

export function isSensitiveEnvVar(key: string, value: string, explicit?: boolean): boolean {
  if (explicit === true) return true;
  return SECRET_KEY_RE.test(key) || CREDENTIALED_URL_RE.test(value);
}

export function parseDotEnv(content: string): EnvironmentVariableItem[] {
  const items: EnvironmentVariableItem[] = [];
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eqIdx = line.indexOf("=");
    if (eqIdx <= 0) continue;
    const key = line.slice(0, eqIdx).trim();
    const val = line.slice(eqIdx + 1).trim().replace(/^["']|["']$/g, "");
    items.push({ key, value: val });
  }
  return items;
}

export function EnvironmentVariables({
  variables,
  source = ".env",
  className,
}: EnvironmentVariablesProps) {
  const [revealedKeys, setRevealedKeys] = React.useState<Record<string, boolean>>({});
  const [copiedKey, setCopiedKey] = React.useState<string | null>(null);

  const toggleReveal = (key: string) => {
    setRevealedKeys((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleCopy = async (key: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 1500);
    } catch {
      // ignore
    }
  };

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card text-xs",
        className
      )}
    >
      <div className="flex items-center justify-between border-b border-border bg-muted/40 px-3 py-2">
        <div className="flex items-center gap-2">
          <KeyRoundIcon className="size-3.5 text-primary" aria-hidden="true" />
          <span className="font-semibold">Environment Variables</span>
        </div>
        <Badge variant="outline" className="font-mono text-[10px]">
          {source}
        </Badge>
      </div>

      {variables.length === 0 ? (
        <div className="p-3 text-muted-foreground">No environment variables defined.</div>
      ) : (
        <div className="divide-y divide-border/60">
          {variables.map((item) => {
            const sensitive = isSensitiveEnvVar(item.key, item.value, item.isSecret);
            const isRevealed = Boolean(revealedKeys[item.key]);
            const displayVal = sensitive && !isRevealed ? "••••••••" : item.value;

            return (
              <div
                key={item.key}
                className="flex items-center justify-between gap-2 px-3 py-2"
              >
                <div className="min-w-0 flex-1 font-mono text-[11px]">
                  <span className="font-semibold text-foreground">{item.key}</span>
                  <span className="mx-1.5 text-muted-foreground">=</span>
                  <span
                    data-testid={`env-val-${item.key}`}
                    className="break-all text-muted-foreground"
                  >
                    {displayVal}
                  </span>
                </div>

                <div className="flex shrink-0 items-center gap-1">
                  {sensitive && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label={isRevealed ? `Hide ${item.key}` : `Reveal ${item.key}`}
                      aria-pressed={isRevealed}
                      onClick={() => toggleReveal(item.key)}
                      className="size-6"
                    >
                      {isRevealed ? (
                        <EyeOffIcon className="size-3" aria-hidden="true" />
                      ) : (
                        <EyeIcon className="size-3" aria-hidden="true" />
                      )}
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Copy ${item.key}`}
                    onClick={() => void handleCopy(item.key, item.value)}
                    className="size-6"
                  >
                    {copiedKey === item.key ? (
                      <CheckIcon className="size-3 text-emerald-500" aria-hidden="true" />
                    ) : (
                      <CopyIcon className="size-3" aria-hidden="true" />
                    )}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
