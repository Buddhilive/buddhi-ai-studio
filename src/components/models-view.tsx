"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { modelsApi, ModelInfo } from "@/lib/api/models";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Trash2Icon, XCircleIcon, DownloadIcon, RefreshCcwIcon, AlertCircleIcon, CheckCircleIcon, BrainCircuitIcon } from "lucide-react";

// ─── Static recommended model catalogue ──────────────────────────────────────

interface RecommendedModel {
  model_id: string;
  quantization: string;
  label: string;
  description: string;
  type: "language" | "embedding";
}

const RECOMMENDED_MODELS: RecommendedModel[] = [
  {
    model_id: "unsloth/Qwen3.5-2B-GGUF",
    quantization: "Q4_K_M",
    label: "Qwen 3.5 2B",
    description: "Lightweight language model optimised for fast inference on CPU.",
    type: "language",
  },
  {
    model_id: "ggml-org/bge-small-en-v1.5-Q8_0-GGUF",
    quantization: "Q8_0",
    label: "BGE Small",
    description: "Compact embedding model for semantic search and retrieval tasks.",
    type: "embedding",
  },
];

// ─── Root view ────────────────────────────────────────────────────────────────

export function ModelsView() {
  const [installedModels, setInstalledModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendError, setBackendError] = useState<string | null>(null);

  const fetchModels = useCallback(async () => {
    try {
      setLoading(true);
      setBackendError(null);
      const data = await modelsApi.listModels();
      setInstalledModels(data || []);
    } catch (err: unknown) {
      const msg = (err as Error).message || "Failed to connect to backend";
      setBackendError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleInstalled = (newModel: ModelInfo) => {
    setInstalledModels(prev => {
      const idx = prev.findIndex(m => m.id === newModel.id);
      if (idx !== -1) {
        const next = [...prev];
        next[idx] = newModel;
        return next;
      }
      return [...prev, newModel];
    });
  };

  const handleDeleted = (id: string) => {
    setInstalledModels(prev => prev.filter(m => m.id !== id));
  };

  const handleUpdated = (id: string, updates: Partial<ModelInfo>) => {
    setInstalledModels(prev =>
      prev.map(m => (m.id === id ? { ...m, ...updates } : m))
    );
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Models</h1>
          <p className="text-muted-foreground">
            Install and manage AI models for use in Buddhi AI Studio.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchModels} disabled={loading}>
          <RefreshCcwIcon className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {backendError && (
        <div className="flex items-center gap-3 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircleIcon className="h-4 w-4 shrink-0" />
          <span>Backend unavailable: {backendError}. Make sure the API server is running.</span>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {RECOMMENDED_MODELS.map(m => (
            <Card key={m.model_id} className="animate-pulse opacity-60">
              <CardHeader>
                <div className="h-5 w-32 rounded bg-muted" />
                <div className="h-4 w-48 rounded bg-muted" />
              </CardHeader>
              <CardContent>
                <div className="h-4 w-full rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {RECOMMENDED_MODELS.map(recommended => {
            const installed = installedModels.find(
              m => m.model_id === recommended.model_id || m.id === recommended.model_id.replace("/", "_")
            ) ?? null;
            return (
              <ModelCard
                key={recommended.model_id}
                recommended={recommended}
                installed={installed}
                backendAvailable={!backendError}
                onInstalled={handleInstalled}
                onDeleted={handleDeleted}
                onUpdated={handleUpdated}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Per-model card ───────────────────────────────────────────────────────────

interface ModelCardProps {
  recommended: RecommendedModel;
  installed: ModelInfo | null;
  backendAvailable: boolean;
  onInstalled: (m: ModelInfo) => void;
  onDeleted: (id: string) => void;
  onUpdated: (id: string, updates: Partial<ModelInfo>) => void;
}

function ModelCard({
  recommended,
  installed,
  backendAvailable,
  onInstalled,
  onDeleted,
  onUpdated,
}: ModelCardProps) {
  const [localProgress, setLocalProgress] = useState(installed?.progress ?? 0);
  const [localStatus, setLocalStatus] = useState<ModelInfo["status"] | "not_installed">(
    installed ? installed.status : "not_installed"
  );
  const [isInstalling, setIsInstalling] = useState(false);
  const [isCanceling, setIsCanceling] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const installedIdRef = useRef<string | null>(installed?.id ?? null);
  const onUpdatedRef = useRef(onUpdated);
  useEffect(() => { onUpdatedRef.current = onUpdated; });

  // Sync external state changes (e.g. after refresh)
  useEffect(() => {
    installedIdRef.current = installed?.id ?? null;
    if (!installed) {
      setLocalStatus("not_installed");
      setLocalProgress(0);
    } else {
      setLocalStatus(installed.status);
      setLocalProgress(installed.progress ?? 0);
    }
  }, [installed]);

  // SSE / polling for active downloads
  useEffect(() => {
    const currentId = installedIdRef.current;
    if (!currentId) return;

    if (localStatus === "pending") {
      // Keep retrying until backend transitions out of "pending".
      // A single one-shot setTimeout would stop if the first poll still returns
      // "pending" (React bails out on same-value setState, so the effect never
      // re-runs and the model gets stuck in the "pending" UI state forever).
      let cancelled = false;
      const doPoll = async () => {
        if (cancelled) return;
        try {
          const data = await modelsApi.getModelStatus(currentId);
          if (cancelled) return;
          if (data.status !== "pending") {
            setLocalStatus(data.status);
            setLocalProgress(data.progress ?? 0);
            onUpdatedRef.current(currentId, { status: data.status, progress: data.progress });
          } else {
            setTimeout(doPoll, 1000); // still pending — retry
          }
        } catch {
          if (!cancelled) setTimeout(doPoll, 2000); // network error — back off
        }
      };
      const timer = setTimeout(doPoll, 1000);
      return () => { cancelled = true; clearTimeout(timer); };
    }

    if (localStatus === "downloading") {
      const url = modelsApi.getProgressUrl(currentId);
      const sse = new EventSource(url);

      sse.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.progress !== undefined) {
            setLocalProgress(data.progress);
            onUpdatedRef.current(currentId, { progress: data.progress });
          }
          if (data.status) {
            setLocalStatus(data.status);
            onUpdatedRef.current(currentId, { status: data.status });
            if (["completed", "failed", "corrupted"].includes(data.status)) {
              sse.close();
            }
          }
        } catch {
          console.error("SSE parse error");
        }
      };

      sse.onerror = () => {
        sse.close();
        modelsApi.getModelStatus(currentId).then(data => {
          setLocalStatus(data.status);
          setLocalProgress(data.progress ?? 0);
          onUpdatedRef.current(currentId, { status: data.status, progress: data.progress });
        }).catch(() => { });
      };

      return () => sse.close();
    }
  }, [localStatus]);

  const handleInstall = async () => {
    try {
      setIsInstalling(true);
      const result = await modelsApi.downloadModel({
        model_id: recommended.model_id,
        quantization: recommended.quantization,
      });
      installedIdRef.current = result.id;
      setLocalStatus(result.status);
      setLocalProgress(result.progress ?? 0);
      onInstalled(result);
      toast.success(`Download started for ${recommended.label}`);
    } catch (err: unknown) {
      const error = err as Error;
      const msg = error.message || "Failed to start download";
      toast.error(msg);
    } finally {
      setIsInstalling(false);
    }
  };

  const handleCancel = async () => {
    const id = installedIdRef.current;
    if (!id) return;
    try {
      setIsCanceling(true);
      await modelsApi.deleteModel(id);
      setLocalStatus("not_installed");
      setLocalProgress(0);
      installedIdRef.current = null;
      onDeleted(id);
      toast.success(`Cancelled download for ${recommended.label}`);
    } catch (err: unknown) {
      toast.error((err as Error).message || "Failed to cancel download");
    } finally {
      setIsCanceling(false);
    }
  };

  const handleDelete = async () => {
    const id = installedIdRef.current;
    if (!id) return;
    try {
      setIsDeleting(true);
      await modelsApi.deleteModel(id);
      setLocalStatus("not_installed");
      setLocalProgress(0);
      installedIdRef.current = null;
      onDeleted(id);
      setDeleteDialogOpen(false);
      toast.success(`Deleted ${recommended.label}`);
    } catch (err: unknown) {
      toast.error((err as Error).message || "Failed to delete model");
    } finally {
      setIsDeleting(false);
    }
  };

  const inProgress = localStatus === "downloading" || localStatus === "pending";

  return (
    <>
      <Card className="flex flex-col">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <BrainCircuitIcon className="h-5 w-5 text-muted-foreground shrink-0" />
              <CardTitle className="text-base leading-snug">{recommended.label}</CardTitle>
            </div>
            <StatusBadge status={localStatus} />
          </div>
          <CardDescription className="text-xs">
            {recommended.model_id}
          </CardDescription>
        </CardHeader>

        <CardContent className="flex-1 space-y-3">
          <p className="text-sm text-muted-foreground">{recommended.description}</p>

          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs font-mono">
              {recommended.quantization}
            </Badge>
            <Badge variant="outline" className="text-xs capitalize">
              {recommended.type}
            </Badge>
          </div>

          {inProgress && (
            <div className="flex items-center gap-2">
              <Progress value={localProgress} className="h-1.5" />
              <p className="text-xs text-muted-foreground text-right">
                {localProgress}%
              </p>
            </div>
          )}

          {localStatus === "failed" && (
            <div className="flex items-center gap-2 text-xs text-destructive">
              <AlertCircleIcon className="h-3.5 w-3.5 shrink-0" />
              <span>Download failed. Try installing again.</span>
            </div>
          )}

          {localStatus === "corrupted" && (
            <div className="flex items-center gap-2 text-xs text-destructive">
              <AlertCircleIcon className="h-3.5 w-3.5 shrink-0" />
              <span>Model file is corrupted. Delete and reinstall.</span>
            </div>
          )}
        </CardContent>

        <CardFooter>
          {localStatus === "not_installed" || localStatus === "failed" || localStatus === "corrupted" ? (
            <Button
              className="w-full"
              size="sm"
              onClick={handleInstall}
              disabled={isInstalling || !backendAvailable}
            >
              {isInstalling ? (
                <RefreshCcwIcon className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <DownloadIcon className="mr-2 h-4 w-4" />
              )}
              {localStatus === "failed" || localStatus === "corrupted" ? "Retry Install" : "Install"}
            </Button>
          ) : inProgress ? (
            <Button
              className="w-full"
              variant="outline"
              size="sm"
              onClick={handleCancel}
              disabled={isCanceling}
            >
              {isCanceling ? (
                <RefreshCcwIcon className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <XCircleIcon className="mr-2 h-4 w-4" />
              )}
              Cancel
            </Button>
          ) : localStatus === "completed" ? (
            <Button
              className="w-full"
              variant="outline"
              size="sm"
              onClick={() => setDeleteDialogOpen(true)}
            >
              <Trash2Icon className="mr-2 h-4 w-4 text-destructive" />
              <span className="text-destructive">Uninstall</span>
            </Button>
          ) : null}
        </CardFooter>
      </Card>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Uninstall {recommended.label}?</DialogTitle>
            <DialogDescription>
              This will permanently delete the model files from disk. You can
              reinstall the model at any time.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? (
                <RefreshCcwIcon className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Trash2Icon className="mr-2 h-4 w-4" />
              )}
              Uninstall
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: ModelInfo["status"] | "not_installed" }) {
  switch (status) {
    case "completed":
      return (
        <Badge className="bg-green-600 text-white shrink-0 gap-1">
          <CheckCircleIcon className="h-3 w-3" />
          Installed
        </Badge>
      );
    case "downloading":
      return <Badge variant="secondary" className="animate-pulse shrink-0">Downloading</Badge>;
    case "pending":
      return <Badge variant="outline" className="shrink-0">Pending</Badge>;
    case "failed":
      return <Badge variant="destructive" className="shrink-0">Failed</Badge>;
    case "corrupted":
      return <Badge variant="destructive" className="shrink-0">Corrupted</Badge>;
    case "not_installed":
    default:
      return <Badge variant="outline" className="text-muted-foreground shrink-0">Not Installed</Badge>;
  }
}
