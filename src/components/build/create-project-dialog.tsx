"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2Icon, PlusIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

export type BuildTemplate = "nextjs-vibe" | "python-blank" | "node-blank";
export type BuildDbDialect = "postgresql" | "sqlite";

interface CreateProjectDialogProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  trigger?: React.ReactNode;
}

export function CreateProjectDialog({
  open: controlledOpen,
  onOpenChange,
  trigger,
}: CreateProjectDialogProps) {
  const router = useRouter();
  const [internalOpen, setInternalOpen] = React.useState(false);
  const open = controlledOpen ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;

  const nameId = React.useId();
  const descId = React.useId();
  const templateId = React.useId();
  const dialectId = React.useId();

  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [template, setTemplate] = React.useState<BuildTemplate>("nextjs-vibe");
  const [dbDialect, setDbDialect] = React.useState<BuildDbDialect>("postgresql");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);
  const [statusMessage, setStatusMessage] = React.useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setErrorMsg("Project name is required.");
      return;
    }
    if (trimmedName.length > 80) {
      setErrorMsg("Project name must be 80 characters or fewer.");
      return;
    }

    setErrorMsg(null);
    setIsSubmitting(true);
    setStatusMessage("Creating project and starting OpenSandbox container...");

    try {
      const res = await fetch("/api/build/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: trimmedName,
          description: description.trim(),
          template,
          db_dialect: dbDialect,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const detail =
          errData?.error?.message || errData?.detail || errData?.error || "Failed to create project";
        setErrorMsg(String(detail));
        setStatusMessage("Project creation failed.");
        return;
      }

      const data = await res.json();
      const projectId = data?.project?.id;
      if (!projectId) {
        setErrorMsg("Invalid response from server.");
        return;
      }

      if (description.trim() && typeof window !== "undefined") {
        window.sessionStorage.setItem(
          `buddhi:initial-prompt:${projectId}`,
          description.trim()
        );
      }

      setStatusMessage("Project created. Redirecting to workspace...");
      setOpen(false);
      setName("");
      setDescription("");
      router.push(`/build/project/${encodeURIComponent(projectId)}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network error";
      setErrorMsg(msg);
      toast.error("Failed to create project", { description: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger !== undefined ? (
        trigger
      ) : (
        <DialogTrigger
          render={
            <Button size="sm" className="gap-1.5">
              <PlusIcon className="size-4" aria-hidden="true" />
              <span>Create New</span>
            </Button>
          }
        />
      )}
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Create New Project</DialogTitle>
          <DialogDescription>
            Provision an isolated OpenSandbox container and start building with BuddhiAI.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor={nameId}>Project Name</Label>
            <Input
              id={nameId}
              placeholder="e.g. Task Tracker App"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={80}
              required
              disabled={isSubmitting}
              aria-invalid={Boolean(errorMsg)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor={descId}>Description / Initial Prompt (optional)</Label>
            <Textarea
              id={descId}
              placeholder="Describe what you want to build. If provided, this will be sent as your first prompt."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              disabled={isSubmitting}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor={templateId}>Starter Template</Label>
              <Select
                value={template}
                onValueChange={(v) => setTemplate((v as BuildTemplate) || "nextjs-vibe")}
                disabled={isSubmitting}
              >
                <SelectTrigger id={templateId} className="w-full">
                  <SelectValue placeholder="Select template" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="nextjs-vibe">Next.js 16+ Vibe Starter</SelectItem>
                  <SelectItem value="python-blank">Blank Python Workspace</SelectItem>
                  <SelectItem value="node-blank">Blank Node.js Workspace</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={dialectId}>Database Dialect</Label>
              <Select
                value={dbDialect}
                onValueChange={(v) => setDbDialect((v as BuildDbDialect) || "postgresql")}
                disabled={isSubmitting}
              >
                <SelectTrigger id={dialectId} className="w-full">
                  <SelectValue placeholder="Select database" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="postgresql">PostgreSQL</SelectItem>
                  <SelectItem value="sqlite">SQLite</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {errorMsg && (
            <p role="alert" className="text-xs font-medium text-destructive">
              {errorMsg}
            </p>
          )}

          <div aria-live="polite" className="sr-only">
            {statusMessage}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting} aria-busy={isSubmitting}>
              {isSubmitting && (
                <Loader2Icon className="mr-1.5 size-4 animate-spin" aria-hidden="true" />
              )}
              <span>{isSubmitting ? "Creating..." : "Create & Start"}</span>
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
