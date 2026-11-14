"use client";

import { useId } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ShieldCheckIcon, ScaleIcon } from "lucide-react";

export interface EgmConfig {
  enabled: boolean;
  max_review_rounds: number;
  goldfish_concurrency: number;
  reviewer_timeout_s: number;
  context_budget_tokens: number;
  enable_brainstorm: boolean;
  default_skill_mode: "standard" | "brainstorm" | "bootstrap" | "drift_report";
}

interface EgmSettingsProps {
  config: EgmConfig;
  onChange: (updated: EgmConfig) => void;
  disabled?: boolean;
}

export function EgmSettings({ config, onChange, disabled }: EgmSettingsProps) {
  const enabledId = useId();
  const roundsId = useId();
  const concurrencyId = useId();
  const brainstormId = useId();

  const handleToggle = (checked: boolean) => {
    onChange({ ...config, enabled: checked });
  };

  const worstCaseCalls = config.max_review_rounds * 5;

  return (
    <Card className="border-border">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheckIcon className="size-5 text-primary" aria-hidden="true" />
            <CardTitle className="text-base font-semibold">
              Elephant-Goldfish Model (Spec-Driven SDD)
            </CardTitle>
          </div>
          <Badge variant={config.enabled ? "default" : "secondary"}>
            {config.enabled ? "Active" : "Disabled"}
          </Badge>
        </div>
        <CardDescription className="max-w-[65ch] text-xs text-muted-foreground">
          Enforces a disciplined dual-agent cognitive architecture. The deep-context <strong>Elephant</strong> drafts
          technical specifications, while stateless, zero-context <strong>Goldfish</strong> reviewers audit against
          quality rubrics before any code is written.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Master Toggle */}
        <div className="flex items-center justify-between rounded-lg border border-border p-3">
          <div className="space-y-0.5">
            <Label htmlFor={enabledId} className="text-sm font-medium cursor-pointer">
              Enable Spec-First EGM Mode by default
            </Label>
            <p className="text-xs text-muted-foreground">
              When active, coding runs draft specifications and pass through Goldfish review gates before implementation.
            </p>
          </div>
          <Switch
            id={enabledId}
            checked={config.enabled}
            onCheckedChange={handleToggle}
            disabled={disabled}
          />
        </div>

        {/* Max Review Rounds Slider */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor={roundsId} className="text-sm font-medium">
              Maximum Sharpening Rounds: <span className="font-mono text-primary font-bold">{config.max_review_rounds}</span>
            </Label>
            <span className="text-xs text-muted-foreground">1 to 5 rounds</span>
          </div>
          <input
            id={roundsId}
            type="range"
            min={1}
            max={5}
            step={1}
            value={config.max_review_rounds}
            onChange={(e) => onChange({ ...config, max_review_rounds: parseInt(e.target.value, 10) })}
            aria-valuemin={1}
            aria-valuemax={5}
            aria-valuenow={config.max_review_rounds}
            aria-valuetext={`${config.max_review_rounds} review rounds`}
            className="w-full accent-primary focus:outline-none focus:ring-2 focus:ring-primary rounded"
            disabled={disabled || !config.enabled}
          />
        </div>

        {/* Reviewer Concurrency & Brainstorm Toggle */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor={concurrencyId} className="text-sm font-medium">
              Goldfish Reviewer Concurrency
            </Label>
            <Select
              value={String(config.goldfish_concurrency)}
              onValueChange={(val) => onChange({ ...config, goldfish_concurrency: parseInt(val || "1", 10) })}
              disabled={disabled || !config.enabled}
            >
              <SelectTrigger id={concurrencyId} className="w-full">
                <SelectValue placeholder="Select concurrency" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1">1 (Sequential - Recommended for CPU)</SelectItem>
                <SelectItem value="2">2 (Balanced)</SelectItem>
                <SelectItem value="4">4 (High Concurrency - GPU)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <div className="space-y-0.5">
              <Label htmlFor={brainstormId} className="text-sm font-medium cursor-pointer">
                7-Lens Concept Brainstorm
              </Label>
              <p className="text-xs text-muted-foreground">
                Run pre-draft ideation swarm before specification.
              </p>
            </div>
            <Switch
              id={brainstormId}
              checked={config.enable_brainstorm}
              onCheckedChange={(checked) => onChange({ ...config, enable_brainstorm: checked })}
              disabled={disabled || !config.enabled}
            />
          </div>
        </div>

        {/* Live Estimate readout */}
        <Alert aria-live="polite" className="border-border bg-muted/40 text-xs">
          <ScaleIcon className="size-4 text-primary" aria-hidden="true" />
          <AlertTitle className="text-xs font-semibold">Review Budget Telemetry</AlertTitle>
          <AlertDescription className="text-xs text-muted-foreground">
            A full 5-stage review pipeline executes up to{" "}
            <strong className="text-foreground">{worstCaseCalls}</strong> Goldfish audits across {config.max_review_rounds} rounds.
            Reviewer concurrency is capped at {config.goldfish_concurrency} worker(s) to protect local CPU memory.
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}
