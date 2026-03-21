"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { modelsApi, ModelInfo } from "@/lib/api/models";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Trash2Icon, XCircleIcon, DownloadIcon, RefreshCcwIcon } from "lucide-react";

export function ModelsView() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchModels = useCallback(async () => {
    try {
      setLoading(true);
      const data = await modelsApi.listModels();
      setModels(data || []);
    } catch (err: unknown) {
      const error = err as Error;
      toast.error(error.message || "Failed to fetch models");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleDownloadCreated = (newModel: ModelInfo) => {
    setModels(prev => {
      // replace if exists, else add
      const idx = prev.findIndex(m => m.id === newModel.id);
      if (idx !== -1) {
        const next = [...prev];
        next[idx] = newModel;
        return next;
      }
      return [newModel, ...prev];
    });
  };

  const removeModelFromList = (id: string) => {
    setModels(prev => prev.filter(m => m.id !== id));
  };
  
  const updateModelStatus = useCallback((id: string, updates: Partial<ModelInfo>) => {
      setModels(prev => prev.map(m => m.id === id ? { ...m, ...updates } : m));
  }, []);

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Models</h1>
        <p className="text-muted-foreground">Manage your AI models and downloads.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <DownloadForm onDownloadStarted={handleDownloadCreated} />
        </div>
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Downloaded Models</CardTitle>
                <CardDescription>View and manage your active and completed model downloads.</CardDescription>
              </div>
              <Button variant="outline" size="icon" onClick={fetchModels} disabled={loading}>
                <RefreshCcwIcon className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </CardHeader>
            <CardContent>
              <ModelsTable 
                models={models} 
                onRemove={removeModelFromList} 
                onUpdate={updateModelStatus}
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function DownloadForm({ onDownloadStarted }: { onDownloadStarted: (m: ModelInfo) => void }) {
  const [modelId, setModelId] = useState("");
  const [quantization, setQuantization] = useState("Q4_K_M");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modelId.trim()) {
      toast.error("Model ID is required");
      return;
    }

    try {
      setIsSubmitting(true);
      const result = await modelsApi.downloadModel({ model_id: modelId, quantization });
      toast.success(`Download started for ${modelId}`);
      onDownloadStarted(result);
      setModelId("");
    } catch (err: unknown) {
      const error = err as Error;
      toast.error(error.message || "Failed to start download");
      console.error("Download error:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Download Model</CardTitle>
        <CardDescription>Initiate a new model download from the hub.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="model_id">Model ID</Label>
            <Input 
              id="model_id" 
              placeholder="e.g. gpt2, llama-2-7b" 
              value={modelId} 
              onChange={(e) => setModelId(e.target.value)} 
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="quantization">Quantization</Label>
            <Select value={quantization} onValueChange={setQuantization}>
              <SelectTrigger>
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Q4_K_M">Q4_K_M (Recommended)</SelectItem>
                <SelectItem value="Q5_K_M">Q5_K_M</SelectItem>
                <SelectItem value="Q8_0">Q8_0</SelectItem>
                <SelectItem value="F16">F16 (Large)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? (
              <RefreshCcwIcon className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <DownloadIcon className="mr-2 h-4 w-4" />
            )}
            Start Download
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function ModelsTable({ models, onRemove, onUpdate }: { models: ModelInfo[], onRemove: (id: string) => void, onUpdate: (id: string, updates: Partial<ModelInfo>) => void }) {
  if (models.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground border border-dashed rounded-lg">
        No models found.
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Model ID</TableHead>
            <TableHead>Quantization</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Progress</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {models.map((model) => (
            <ModelTableRow 
              key={model.id} 
              model={model} 
              onRemove={() => onRemove(model.id)}
              onUpdate={(updates) => onUpdate(model.id, updates)}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ModelTableRow({ model, onRemove, onUpdate }: { model: ModelInfo; onRemove: () => void; onUpdate: (updates: Partial<ModelInfo>) => void }) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [isCanceling, setIsCanceling] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const [localProgress, setLocalProgress] = useState(model.progress || 0);
  const [localStatus, setLocalStatus] = useState(model.status);

  // Keep a stable ref to onUpdate so it doesn't retrigger the SSE effect
  const onUpdateRef = useRef(onUpdate);
  useEffect(() => { onUpdateRef.current = onUpdate; });

  useEffect(() => {
    // Only open SSE when the backend is actively streaming (status=downloading)
    // When status is 'pending', poll until it transitions to 'downloading'
    if (localStatus === 'pending') {
      const pollTimer = setTimeout(async () => {
        try {
          const statusData = await modelsApi.getModelStatus(model.id);
          setLocalStatus(statusData.status);
          setLocalProgress(statusData.progress || 0);
          onUpdateRef.current({ status: statusData.status, progress: statusData.progress });
        } catch (e) {}
      }, 1000);
      return () => clearTimeout(pollTimer);
    }

    if (localStatus === 'downloading') {
      const url = modelsApi.getProgressUrl(model.id);
      const sse = new EventSource(url);
      eventSourceRef.current = sse;

      sse.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.progress !== undefined) {
             setLocalProgress(data.progress);
             onUpdateRef.current({ progress: data.progress });
          }
          if (data.status) {
             setLocalStatus(data.status);
             onUpdateRef.current({ status: data.status });
             if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
                 sse.close();
             }
          }
        } catch (err) {
            console.error("SSE parse error", err);
        }
      };

      sse.onerror = () => {
        sse.close();
        // Fallback: poll the status once via API
        modelsApi.getModelStatus(model.id).then((statusData) => {
          setLocalStatus(statusData.status);
          setLocalProgress(statusData.progress || 0);
          onUpdateRef.current({ status: statusData.status, progress: statusData.progress });
        }).catch(() => {});
      };

      return () => {
        sse.close();
        eventSourceRef.current = null;
      };
    }
  }, [localStatus, model.id]);

  const handleCancel = async () => {
    try {
      setIsCanceling(true);
      await modelsApi.deleteModel(model.id);
      toast.success(`Cancelled download for ${model.model_id || model.id}`);
      setLocalStatus('cancelled');
      onUpdate({ status: 'cancelled' });
      if (eventSourceRef.current) {
         eventSourceRef.current.close();
      }
    } catch (err: unknown) {
      const error = err as Error;
      toast.error(error.message || "Failed to cancel download");
      console.error(err);
    } finally {
      setIsCanceling(false);
    }
  };

  const handleDelete = async () => {
    try {
      setIsDeleting(true);
      await modelsApi.deleteModel(model.id);
      toast.success(`Deleted model ${model.model_id || model.id}`);
      onRemove();
    } catch (err: unknown) {
      const error = err as Error;
      toast.error(error.message || "Failed to delete files");
      console.error(err);
    } finally {
      setIsDeleting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed': return <Badge variant="default" className="bg-green-600">Completed</Badge>;
      case 'downloading': return <Badge variant="secondary" className="animate-pulse">Downloading</Badge>;
      case 'pending': return <Badge variant="outline">Pending</Badge>;
      case 'failed': return <Badge variant="destructive">Failed</Badge>;
      case 'cancelled': return <Badge variant="secondary" className="bg-gray-500">Cancelled</Badge>;
      default: return <Badge variant="outline">{status}</Badge>;
    }
  };

  const inProgress = localStatus === 'downloading' || localStatus === 'pending';

  return (
    <TableRow>
      <TableCell className="font-medium">{model.model_id || model.id}</TableCell>
      <TableCell>{model.quantization || '-'}</TableCell>
      <TableCell>{getStatusBadge(localStatus)}</TableCell>
      <TableCell>
        {inProgress ? (
          <div className="flex items-center gap-2">
            <Progress value={localProgress} className="h-2 w-[100px]" />
            <span className="text-xs text-muted-foreground">{Math.round(localProgress)}%</span>
          </div>
        ) : (
             <span className="text-xs text-muted-foreground">{localProgress}%</span>
        )}
      </TableCell>
      <TableCell className="text-right space-x-2">
        {inProgress ? (
          <Button variant="ghost" size="icon" onClick={handleCancel} disabled={isCanceling} title="Cancel Download">
             <XCircleIcon className={`h-4 w-4 text-red-500 ${isCanceling ? 'opacity-50' : ''}`} />
          </Button>
        ) : (
          <Button variant="ghost" size="icon" onClick={handleDelete} disabled={isDeleting} title="Delete Model Files">
             <Trash2Icon className={`h-4 w-4 text-red-500 ${isDeleting ? 'opacity-50' : ''}`} />
          </Button>
        )}
      </TableCell>
    </TableRow>
  );
}
