"use client";

import { useId } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { CpuIcon, LayersIcon, SparklesIcon, ShieldAlertIcon } from "lucide-react";

export interface RlmConfig {
  enabled: boolean;
  mode: "auto" | "always" | "never";
  max_depth: number;
  snippet_tokens: number;
  max_subcalls: number;
  subcall_concurrency: number;
  auto_threshold_ratio: number;
  prompt_reserve_tokens: number;
  effective_reach_tokens: number;
  fan_out: number;
  bounded_by_budget: boolean;
}

interface RlmSettingsProps {
  config: RlmConfig;
  onChange: (updated: RlmConfig) => void;
  contextWindow: number;
  maxViableTokens?: number;
  modelAssumed?: string;
}

export function RlmSettings({
  config,
  onChange,
  contextWindow,
  maxViableTokens,
  modelAssumed = "Gemma 4 E4B",
}: RlmSettingsProps) {
  const depthId = useId();
  const modeId = useId();
  const snippetId = useId();
  const subcallsId = useId();
  const thresholdId = useId();

  // Compute live client-side estimate if props change before backend sync
  const promptReserve = config.prompt_reserve_tokens || 2048;
  const usableWindow = Math.max(512, contextWindow - promptReserve);
  const fanOut = Math.max(1, Math.floor(usableWindow / (config.snippet_tokens || 2048)));
  const unboundedReach =
    config.max_depth > 0
      ? Math.pow(fanOut, config.max_depth) * config.snippet_tokens
      : usableWindow;
  const budgetBound = config.max_subcalls * config.snippet_tokens;
  const effectiveReach =
    config.max_depth > 0 ? Math.min(unboundedReach, budgetBound) : usableWindow;
  const isBudgetBounded = config.max_depth > 0 && unboundedReach > budgetBound;

  const handleUpdate = (partial: Partial<RlmConfig>) => {
    onChange({
      ...config,
      ...partial,
      effective_reach_tokens: effectiveReach,
      fan_out: fanOut,
      bounded_by_budget: isBudgetBounded,
    });
  };

  const isExceedingViable = maxViableTokens && contextWindow > maxViableTokens;

  return (
    <Card className="border-border">
      <CardHeader>
        <div className="flex items-center gap-2">
          <LayersIcon className="size-5 text-primary" aria-hidden="true" />
          <CardTitle className="text-base">Recursive Language Model (RLM) Scaling</CardTitle>
        </div>
        <CardDescription>
          Enables local {modelAssumed} CPU models to inspect and analyze 200k+ token codebases
          using an isolated OpenSandbox Python REPL and programmatic LiteRT subcalls.
        </CardDescription>
        <CardAction>
          <div className="flex items-center gap-2">
            <Label htmlFor="rlm-enabled-toggle" className="text-xs text-muted-foreground font-normal">
              {config.enabled ? "Enabled" : "Disabled"}
            </Label>
            <Switch
              id="rlm-enabled-toggle"
              checked={config.enabled}
              onCheckedChange={(enabled) => handleUpdate({ enabled })}
              aria-label="Toggle RLM context scaling"
            />
          </div>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        {/* Live Reach Readout Alert */}
        <Alert
          aria-live="polite"
          className="border-primary/20 bg-primary/5 text-foreground"
        >
          <SparklesIcon className="size-4 text-primary" aria-hidden="true" />
          <AlertTitle className="flex items-center gap-2 text-sm font-medium">
            Estimated Effective Context Reach:
            <Badge variant="secondary" className="font-mono text-xs font-semibold">
              ~{effectiveReach.toLocaleString()} tokens
            </Badge>
            <Badge variant="outline" className="text-xs font-normal">
              {fanOut}x fan-out • depth {config.max_depth}
            </Badge>
          </AlertTitle>
          <AlertDescription className="text-xs text-muted-foreground pt-1">
            {config.max_depth === 0 ? (
              "Direct inference without recursion. Prompt is bounded strictly by the model's base context window."
            ) : isBudgetBounded ? (
              `Bounded by task budget cap of ${config.max_subcalls} subcalls × ${config.snippet_tokens.toLocaleString()} tokens/snippet. Increase subcall budget for higher reach.`
            ) : (
              `Synthesizes multi-tier code analysis across ${Math.pow(fanOut, config.max_depth)} potential snippets using the ${contextWindow.toLocaleString()} token base window.`
            )}
          </AlertDescription>
        </Alert>

        {isExceedingViable && (
          <Alert variant="destructive" className="text-xs">
            <ShieldAlertIcon className="size-4" aria-hidden="true" />
            <AlertTitle className="text-sm font-semibold">Hardware Viability Warning</AlertTitle>
            <AlertDescription>
              Current base context window ({contextWindow.toLocaleString()} tokens) exceeds host
              safe RAM capacity ({maxViableTokens?.toLocaleString()} tokens). Reduce context window
              or rely on RLM recursion depth to avoid out-of-memory errors on CPU.
            </AlertDescription>
          </Alert>
        )}

        {/* Activation Mode */}
        <div className="flex flex-col gap-2">
          <Label htmlFor={modeId} className="text-sm font-medium">
            Activation Mode
          </Label>
          <Select
            value={config.mode}
            onValueChange={(val) => {
              if (val) handleUpdate({ mode: val as "auto" | "always" | "never" });
            }}
            disabled={!config.enabled}
          >
            <SelectTrigger id={modeId} className="w-full sm:w-80">
              <SelectValue placeholder="Select mode" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="auto">
                <div className="flex items-center gap-2">
                  <span>Automatic</span>
                  <span className="text-muted-foreground text-xs">(Working set &gt; threshold)</span>
                </div>
              </SelectItem>
              <SelectItem value="always">
                <div className="flex items-center gap-2">
                  <span>Always On</span>
                  <span className="text-muted-foreground text-xs">(Every repository task)</span>
                </div>
              </SelectItem>
              <SelectItem value="never">
                <div className="flex items-center gap-2">
                  <span>Never</span>
                  <span className="text-muted-foreground text-xs">(Standard inference only)</span>
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
          <p className="text-muted-foreground text-xs">
            In Automatic mode, Buddhi switches to RLM when repository working set exceeds 60% of
            the base context window.
          </p>
        </div>

        {/* Recursion Depth Slider */}
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <Label htmlFor={depthId} className="text-sm font-medium">
              Maximum Recursion Depth (`max_depth`)
            </Label>
            <span className="text-xs font-mono font-semibold text-primary">
              Level {config.max_depth} {config.max_depth === 2 && "(Recommended)"}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <input
              id={depthId}
              type="range"
              min={0}
              max={3}
              step={1}
              value={config.max_depth}
              onChange={(e) => handleUpdate({ max_depth: parseInt(e.target.value, 10) })}
              disabled={!config.enabled}
              aria-valuemin={0}
              aria-valuemax={3}
              aria-valuenow={config.max_depth}
              aria-valuetext={`Recursion depth ${config.max_depth}`}
              className="w-full accent-primary h-2 bg-secondary rounded-lg cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <span className="font-mono text-sm w-8 text-center font-bold">
              {config.max_depth}
            </span>
          </div>

          <div className="flex justify-between text-[11px] text-muted-foreground px-0.5">
            <span>0 (Direct)</span>
            <span>1 (~60k)</span>
            <span>2 (~200k+)</span>
            <span>3 (500k+)</span>
          </div>
          <p className="text-muted-foreground text-xs">
            Higher recursion depths allow multi-tier code map summarization on small models without
            increasing prompt size.
          </p>
        </div>

        {/* Snippet Token Size & Subcall Cap */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
          <div className="flex flex-col gap-2">
            <Label htmlFor={snippetId} className="text-sm font-medium">
              Snippet Chunk Size (Tokens)
            </Label>
            <Input
              id={snippetId}
              type="number"
              min={512}
              max={8192}
              step={256}
              value={config.snippet_tokens}
              onChange={(e) =>
                handleUpdate({ snippet_tokens: parseInt(e.target.value, 10) || 2048 })
              }
              disabled={!config.enabled}
              className="font-mono"
            />
            <p className="text-muted-foreground text-xs">
              Token budget per chunk for `chunk_file()` and `llm_query()`.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor={subcallsId} className="text-sm font-medium">
              Max Subcalls per Task
            </Label>
            <Input
              id={subcallsId}
              type="number"
              min={4}
              max={256}
              step={4}
              value={config.max_subcalls}
              onChange={(e) =>
                handleUpdate({ max_subcalls: parseInt(e.target.value, 10) || 32 })
              }
              disabled={!config.enabled}
              className="font-mono"
            />
            <p className="text-muted-foreground text-xs">
              Hard safety ceiling on subcall count per user task to bound CPU time.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
