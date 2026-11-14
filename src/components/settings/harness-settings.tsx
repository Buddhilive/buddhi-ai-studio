"use client";

import * as React from "react";
import { useId, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type {
  ExperienceEntry,
  HarnessComponentKey,
  HarnessOverlay,
  HarnessSettings as HarnessSettingsConfig,
} from "@/lib/agent-events";
import { ChevronDownIcon, ChevronRightIcon, PinIcon, RotateCcwIcon, Trash2Icon } from "lucide-react";
import { toast } from "sonner";

const COMPONENT_KEYS: HarnessComponentKey[] = [
  "system_prompt",
  "guardrails",
  "memory",
  "tool_guidance",
  "subagents",
  "skills",
  "scripts",
  "plugins",
];

interface HarnessSettingsProps {
  config: HarnessSettingsConfig;
  overlay: HarnessOverlay | null;
  history: HarnessOverlay[];
  experiences: ExperienceEntry[];
  onConfigUpdated: (next: HarnessSettingsConfig) => void;
  onRefresh: () => Promise<void>;
}

export function HarnessSettings({
  config,
  overlay,
  history,
  experiences,
  onConfigUpdated,
  onRefresh,
}: HarnessSettingsProps) {
  const baseId = useId();
  const [saving, setSaving] = useState(false);
  const [expandedKey, setExpandedKey] = useState<HarnessComponentKey | null>(null);
  const [confirmAction, setConfirmAction] = useState<
    { type: "reset" } | { type: "rollback"; versionId: string } | null
  >(null);

  const saveConfig = async (patch: Partial<HarnessSettingsConfig>) => {
    const next = { ...config, ...patch };
    setSaving(true);
    try {
      const res = await fetch("/api/settings/harness", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
      });
      if (!res.ok) throw new Error("Failed to save Harness² settings");
      const saved = (await res.json()) as HarnessSettingsConfig;
      onConfigUpdated(saved);
      toast.success("Harness² settings saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleConfirmOverlayAction = async () => {
    if (!confirmAction) return;
    try {
      const res = await fetch("/api/harness/overlay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          confirmAction.type === "reset"
            ? { workspaceId: "default", action: "reset" }
            : { workspaceId: "default", action: "rollback", versionId: confirmAction.versionId }
        ),
      });
      if (!res.ok) throw new Error("Overlay operation failed");
      toast.success(
        confirmAction.type === "reset" ? "Workspace harness reset to baseline" : "Overlay rolled back"
      );
      setConfirmAction(null);
      await onRefresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Overlay operation failed");
    }
  };

  const handleTogglePin = async (entry: ExperienceEntry) => {
    try {
      const res = await fetch("/api/harness/experience", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspaceId: entry.workspace_id,
          entryId: entry.entry_id,
          pinned: !entry.is_pinned,
        }),
      });
      if (!res.ok) throw new Error("Failed to update pin");
      await onRefresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update pin");
    }
  };

  const handleDeleteExperience = async (entry: ExperienceEntry) => {
    try {
      const res = await fetch(
        `/api/harness/experience?workspaceId=${encodeURIComponent(entry.workspace_id)}&entryId=${encodeURIComponent(entry.entry_id)}`,
        { method: "DELETE" }
      );
      if (!res.ok) throw new Error("Failed to delete experience");
      toast.success("Experience lesson removed");
      await onRefresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete experience");
    }
  };

  return (
    <Card className="border border-border bg-card shadow-none">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-base font-semibold">
              Google Harness² Recursive Scaffolding
            </CardTitle>
            <CardDescription className="max-w-[65ch]">
              Adaptive Level 1 Propose–Probe–Compose calibration and Level 2 EXPERIENCE memory around frozen local models. Goldfish verification remains strictly isolated.
            </CardDescription>
          </div>
          {overlay && (
            <Badge variant="outline" className="font-mono text-xs tabular-nums">
              Active: {overlay.version_id}
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Calibration Controls */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex items-center justify-between rounded-md border border-border p-3">
            <div className="space-y-0.5 pr-3">
              <Label htmlFor={`${baseId}-enabled`}>Enable Level 2 Harness² Loading</Label>
              <p className="text-xs text-muted-foreground">
                Zero-cost load of cached overlay &amp; EXPERIENCE at analyze.
              </p>
            </div>
            <Switch
              id={`${baseId}-enabled`}
              checked={config.enabled}
              disabled={saving}
              onCheckedChange={(checked) => saveConfig({ enabled: checked })}
            />
          </div>

          <div className="flex items-center justify-between rounded-md border border-border p-3">
            <div className="space-y-0.5 pr-3">
              <Label htmlFor={`${baseId}-retry`}>Auto-Calibrate on Retry</Label>
              <p className="text-xs text-muted-foreground">
                Run bounded Propose–Probe–Compose when review/verify returns retry.
              </p>
            </div>
            <Switch
              id={`${baseId}-retry`}
              checked={config.auto_calibrate_on_retry}
              disabled={saving}
              onCheckedChange={(checked) => saveConfig({ auto_calibrate_on_retry: checked })}
            />
          </div>

          <div className="space-y-1.5 rounded-md border border-border p-3">
            <Label htmlFor={`${baseId}-candidates`}>Max Probe Candidates (1–3)</Label>
            <Input
              id={`${baseId}-candidates`}
              type="number"
              min={1}
              max={3}
              value={config.max_candidates}
              disabled={saving}
              className="font-mono tabular-nums"
              onChange={(e) => {
                const v = Math.min(3, Math.max(1, Number(e.target.value) || 1));
                void saveConfig({ max_candidates: v });
              }}
            />
          </div>

          <div className="space-y-1.5 rounded-md border border-border p-3">
            <Label htmlFor={`${baseId}-steps`}>Max Steps per Probe (2–15)</Label>
            <Input
              id={`${baseId}-steps`}
              type="number"
              min={2}
              max={15}
              value={config.probe_max_steps}
              disabled={saving}
              className="font-mono tabular-nums"
              onChange={(e) => {
                const v = Math.min(15, Math.max(2, Number(e.target.value) || 6));
                void saveConfig({ probe_max_steps: v });
              }}
            />
          </div>
        </div>

        {/* 8-Component Overlay Inspector */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium">8 Editable Harness Components</h3>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setConfirmAction({ type: "reset" })}
              disabled={!overlay}
            >
              <RotateCcwIcon className="mr-1.5 size-3.5" aria-hidden="true" />
              Reset to Baseline
            </Button>
          </div>
          <div className="divide-y divide-border rounded-md border border-border">
            {COMPONENT_KEYS.map((key) => {
              const isOpen = expandedKey === key;
              const panelId = `${baseId}-panel-${key}`;
              const val = overlay?.components?.[key];
              const isEmpty =
                !val ||
                (typeof val === "string" && val.trim().length === 0) ||
                (Array.isArray(val) && val.length === 0) ||
                (typeof val === "object" && !Array.isArray(val) && Object.keys(val).length === 0);

              return (
                <div key={key}>
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    aria-controls={panelId}
                    onClick={() => setExpandedKey(isOpen ? null : key)}
                    className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-ring"
                  >
                    <span className="flex items-center gap-2 font-mono">
                      {isOpen ? (
                        <ChevronDownIcon className="size-3.5" aria-hidden="true" />
                      ) : (
                        <ChevronRightIcon className="size-3.5" aria-hidden="true" />
                      )}
                      {key}
                    </span>
                    <Badge variant={isEmpty ? "secondary" : "outline"} className="text-[11px]">
                      {isEmpty ? "baseline" : "customized"}
                    </Badge>
                  </button>
                  {isOpen && (
                    <div id={panelId} className="border-t border-border bg-muted/30 px-3 py-2">
                      <pre className="max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[11px] text-foreground">
                        {isEmpty
                          ? "(Using baseline BuddhiAI default)"
                          : typeof val === "string"
                            ? val
                            : JSON.stringify(val, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Snapshot History & Rollback */}
        {history.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Overlay Snapshot History</h3>
            <div
              className="overflow-x-auto rounded-md border border-border"
              tabIndex={0}
              aria-label="Overlay snapshot history table"
            >
              <table className="w-full text-left text-xs">
                <caption className="sr-only">Versioned Harness² overlay snapshots</caption>
                <thead className="border-b border-border bg-muted/40">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">Version</th>
                    <th scope="col" className="px-3 py-2 font-medium">Status</th>
                    <th scope="col" className="px-3 py-2 font-medium">Created</th>
                    <th scope="col" className="px-3 py-2 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border font-mono tabular-nums">
                  {history.slice(0, 8).map((item) => (
                    <tr key={item.version_id}>
                      <th scope="row" className="px-3 py-2 font-normal">{item.version_id}</th>
                      <td className="px-3 py-2">
                        {item.is_active ? "[ACTIVE]" : "[ARCHIVED]"}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {item.created_at.slice(0, 19).replace("T", " ")}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {!item.is_active && (
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              setConfirmAction({ type: "rollback", versionId: item.version_id })
                            }
                          >
                            Rollback
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* EXPERIENCE Library */}
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Level 2 Workspace EXPERIENCE Library</h3>
          {experiences.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No distilled EXPERIENCE lessons yet for this workspace.
            </p>
          ) : (
            <div
              className="overflow-x-auto rounded-md border border-border"
              tabIndex={0}
              aria-label="Workspace EXPERIENCE lessons table"
            >
              <table className="w-full text-left text-xs">
                <caption className="sr-only">Distilled Level 2 EXPERIENCE lessons</caption>
                <thead className="border-b border-border bg-muted/40">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">Signature</th>
                    <th scope="col" className="px-3 py-2 font-medium">Lesson</th>
                    <th scope="col" className="px-3 py-2 font-medium">Score</th>
                    <th scope="col" className="px-3 py-2 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {experiences.map((entry) => (
                    <tr key={entry.entry_id}>
                      <th scope="row" className="px-3 py-2 font-mono font-normal">
                        {entry.task_signature}
                      </th>
                      <td className="max-w-[45ch] px-3 py-2 text-foreground">
                        {entry.lesson}
                      </td>
                      <td className="px-3 py-2 font-mono tabular-nums">
                        {entry.confidence_score.toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <div className="inline-flex items-center gap-1">
                          <Button
                            type="button"
                            variant={entry.is_pinned ? "secondary" : "ghost"}
                            size="sm"
                            aria-label={entry.is_pinned ? `Unpin ${entry.task_signature}` : `Pin ${entry.task_signature}`}
                            aria-pressed={entry.is_pinned}
                            onClick={() => void handleTogglePin(entry)}
                          >
                            <PinIcon className="size-3.5" aria-hidden="true" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            aria-label={`Delete ${entry.task_signature}`}
                            onClick={() => void handleDeleteExperience(entry)}
                          >
                            <Trash2Icon className="size-3.5 text-destructive" aria-hidden="true" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </CardContent>

      <Dialog open={confirmAction !== null} onOpenChange={(open) => !open && setConfirmAction(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {confirmAction?.type === "reset"
                ? "Reset Workspace Harness?"
                : "Rollback Harness Overlay?"}
            </DialogTitle>
            <DialogDescription>
              {confirmAction?.type === "reset"
                ? "This deactivates the current Harness² overlay so future runs use the baseline BuddhiAI scaffolding."
                : `This restores snapshot ${confirmAction?.versionId ?? ""} as the active Harness² overlay.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConfirmAction(null)}>
              Cancel
            </Button>
            <Button type="button" variant="destructive" onClick={() => void handleConfirmOverlayAction()}>
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
