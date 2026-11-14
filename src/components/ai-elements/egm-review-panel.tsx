"use client";

import { useId, useRef, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EgmReviewReport } from "@/lib/agent-events";
import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  InfoIcon,
  OctagonAlertIcon,
  SendIcon,
} from "lucide-react";
import { toast } from "sonner";

interface EgmReviewPanelProps {
  runId: string;
  report: EgmReviewReport;
  specPath?: string;
  onResolved?: () => void;
}

export function EgmReviewPanel({ runId, report, specPath, onResolved }: EgmReviewPanelProps) {
  const panelId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [decisions, setDecisions] = useState<Record<string, "accept" | "reject" | "defer">>({});
  const [rationales, setRationales] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Focus management on mount / interrupt entry (SC-007, FR-016)
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const handleDecision = (findingId: string, choice: "accept" | "reject" | "defer") => {
    setDecisions((prev) => ({ ...prev, [findingId]: choice }));
  };

  const handleRationale = (findingId: string, text: string) => {
    setRationales((prev) => ({ ...prev, [findingId]: text }));
  };

  const handleAcceptAll = () => {
    const updated: Record<string, "accept" | "reject" | "defer"> = {};
    for (const f of report.findings) {
      updated[f.id] = "accept";
    }
    setDecisions(updated);
  };

  const handleSubmit = async (approvePlan: boolean) => {
    setIsSubmitting(true);
    try {
      const decisionList = report.findings.map((f) => ({
        finding_id: f.id,
        decision: decisions[f.id] || "accept",
        rationale: rationales[f.id] || null,
        approve_plan: approvePlan,
      }));

      const res = await fetch(`/api/agent/runs/${runId}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decisions: decisionList,
          approve_for_implementation: approvePlan,
        }),
      });

      if (!res.ok) {
        throw new Error(await res.text());
      }

      toast.success(approvePlan ? "Spec approved! Implementation started." : "Triage submitted. Sharpening spec...");
      onResolved?.();
    } catch (err: unknown) {
      toast.error("Failed to submit resolution", {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const blockerCount = report.findings.filter((f) => f.severity === "blocker").length;
  const majorCount = report.findings.filter((f) => f.severity === "major").length;
  const nitCount = report.findings.filter((f) => f.severity === "nit").length;

  return (
    <section
      role="region"
      aria-labelledby={`${panelId}-heading`}
      tabIndex={-1}
      className="my-4 rounded-lg border border-border bg-card p-4 space-y-4 focus:outline-none focus:ring-2 focus:ring-primary shadow-sm"
    >
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div>
          <h3
            id={`${panelId}-heading`}
            ref={headingRef}
            tabIndex={-1}
            className="text-base font-semibold focus:outline-none"
          >
            Goldfish Review Report & Triage Gate (Round {report.round})
          </h3>
          <p className="text-xs text-muted-foreground">
            Target: <code className="font-mono text-foreground">{specPath || report.artifact_path}</code>
          </p>
        </div>

        {/* Severity Count Badges */}
        <div className="flex items-center gap-1.5 text-xs font-mono">
          {blockerCount > 0 && (
            <Badge className="bg-destructive/10 text-destructive border-destructive/40 font-semibold gap-1">
              <OctagonAlertIcon className="size-3.5" aria-hidden="true" />
              <span>[BLOCKER] {blockerCount}</span>
            </Badge>
          )}
          {majorCount > 0 && (
            <Badge className="bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/40 font-semibold gap-1">
              <AlertTriangleIcon className="size-3.5" aria-hidden="true" />
              <span>[MAJOR] {majorCount}</span>
            </Badge>
          )}
          {nitCount > 0 && (
            <Badge className="bg-sky-500/10 text-sky-800 dark:text-sky-300 border-sky-500/40 font-semibold gap-1">
              <InfoIcon className="size-3.5" aria-hidden="true" />
              <span>[NIT] {nitCount}</span>
            </Badge>
          )}
        </div>
      </div>

      {/* Reviewer Status Table */}
      <div className="rounded border border-border bg-muted/20 p-2 text-xs">
        <div className="font-medium mb-1 text-muted-foreground">Reviewer Evaluation Lenses:</div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(report.reviewer_statuses).map(([lens, st]) => (
            <span key={lens} className="inline-flex items-center gap-1 font-mono text-[11px]">
              {st === "completed" ? (
                <CheckCircle2Icon className="size-3 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
              ) : (
                <OctagonAlertIcon className="size-3 text-destructive" aria-hidden="true" />
              )}
              <span>{lens}: <strong>{st}</strong></span>
            </span>
          ))}
        </div>
      </div>

      {/* Findings List */}
      <div className="space-y-3">
        {report.findings.length === 0 ? (
          <p className="text-xs text-muted-foreground italic">No discrepancies found across evaluated rubrics.</p>
        ) : (
          report.findings.map((finding) => {
            const currentChoice = decisions[finding.id] || "accept";
            const isBlocker = finding.severity === "blocker";
            const isMajor = finding.severity === "major";

            return (
              <fieldset
                key={finding.id}
                className={`rounded-md border p-3 space-y-2 text-xs ${
                  isBlocker
                    ? "border-destructive/50 bg-destructive/5"
                    : isMajor
                    ? "border-amber-500/40 bg-amber-500/5"
                    : "border-border bg-card"
                }`}
              >
                <legend className="sr-only">
                  Finding {finding.id}: {finding.severity} in {finding.scope}
                </legend>

                {/* Finding Title & Badges */}
                <div className="flex flex-wrap items-center justify-between gap-1">
                  <div className="flex items-center gap-2">
                    {isBlocker && (
                      <span className="inline-flex items-center gap-1 text-destructive font-bold text-[11px]">
                        <OctagonAlertIcon className="size-3.5" aria-hidden="true" />
                        [BLOCKER]
                      </span>
                    )}
                    {isMajor && (
                      <span className="inline-flex items-center gap-1 text-amber-700 dark:text-amber-300 font-bold text-[11px]">
                        <AlertTriangleIcon className="size-3.5" aria-hidden="true" />
                        [MAJOR]
                      </span>
                    )}
                    {!isBlocker && !isMajor && (
                      <span className="inline-flex items-center gap-1 text-sky-700 dark:text-sky-300 font-medium text-[11px]">
                        <InfoIcon className="size-3.5" aria-hidden="true" />
                        [NIT]
                      </span>
                    )}
                    <span className="font-mono text-muted-foreground">[{finding.id}]</span>
                    <strong className="text-foreground">{finding.description}</strong>
                  </div>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    Lens: {finding.lens} | Scope: {finding.scope}
                  </span>
                </div>

                <p className="text-muted-foreground max-w-[65ch]">
                  <strong>Recommendation:</strong> {finding.recommendation}
                </p>

                {/* Triage Decision Buttons */}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <span className="text-[11px] font-medium text-muted-foreground mr-1">Decision:</span>
                  {(["accept", "reject", "defer"] as const).map((opt) => (
                    <Button
                      key={opt}
                      type="button"
                      size="sm"
                      variant={currentChoice === opt ? "default" : "outline"}
                      aria-pressed={currentChoice === opt}
                      onClick={() => handleDecision(finding.id, opt)}
                      className="h-7 px-2.5 text-[11px] capitalize"
                    >
                      {opt}
                    </Button>
                  ))}

                  <Input
                    type="text"
                    placeholder="Optional rationale/notes..."
                    value={rationales[finding.id] || ""}
                    onChange={(e) => handleRationale(finding.id, e.target.value)}
                    className="h-7 text-[11px] w-48 ml-auto"
                  />
                </div>
              </fieldset>
            );
          })
        )}
      </div>

      {/* Action Footer */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={handleAcceptAll}
          className="text-xs"
        >
          Accept All Findings
        </Button>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={isSubmitting}
            onClick={() => handleSubmit(false)}
            className="text-xs"
          >
            Apply Revisions & Re-Review
          </Button>

          <Button
            type="button"
            size="sm"
            disabled={isSubmitting}
            onClick={() => handleSubmit(true)}
            className="text-xs font-semibold gap-1.5"
          >
            <SendIcon className="size-3.5" aria-hidden="true" />
            Approve Spec & Implement
          </Button>
        </div>
      </div>
    </section>
  );
}
