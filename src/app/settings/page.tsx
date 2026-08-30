"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { CpuIcon, KeyIcon, Loader2Icon, SparklesIcon } from "lucide-react";
import { toast } from "sonner";

interface SupportedBackend {
  id: string;
  name: string;
  supported: boolean;
  recommended: boolean;
  reason?: string | null;
}

interface SystemResources {
  total_memory_bytes: number;
  available_memory_bytes: number;
  cpu_count: number;
  gpu_name?: string | null;
  gpu_total_memory_bytes?: number | null;
  gpu_free_memory_bytes?: number | null;
  supported_backends: SupportedBackend[];
  recommended_backend: "cpu" | "gpu" | "npu";
  recommended_max_num_tokens: number;
  max_viable_tokens: number;
  model_assumed: string;
  reasoning: string;
}

const TOKEN_PRESETS = [2048, 4096, 8192, 16384, 32768];

export default function SettingsPage() {
  // Hugging Face Token state
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [token, setToken] = useState("");
  const [isSavingToken, setIsSavingToken] = useState(false);

  // Inference Settings state
  const [litertBackend, setLitertBackend] = useState<string>("cpu");
  const [maxNumToken, setMaxNumToken] = useState<number>(16384);
  const [isSavingInference, setIsSavingInference] = useState(false);

  // System Resource Recommendation state
  const [systemResources, setSystemResources] = useState<SystemResources | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshAll = useCallback(async () => {
    try {
      const [hfRes, infRes, resRes] = await Promise.all([
        fetch("/api/settings/hf-token"),
        fetch("/api/settings/inference"),
        fetch("/api/settings/system-resources"),
      ]);

      if (hfRes.ok) {
        const hfData = await hfRes.json();
        setConfigured(Boolean(hfData.configured));
      }

      if (infRes.ok) {
        const infData = await infRes.json();
        if (infData.litert_backend) setLitertBackend(infData.litert_backend);
        if (infData.max_num_token) setMaxNumToken(infData.max_num_token);
      }

      if (resRes.ok) {
        const resData = await resRes.json();
        setSystemResources(resData);
      }
    } catch (err) {
      console.error("[settings] failed to load settings:", err);
      toast.error("Could not load settings", {
        description: err instanceof Error ? err.message : "The backend may be unreachable.",
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  const handleSaveToken = useCallback(async () => {
    if (!token.trim()) {
      toast.error("Enter a token before saving");
      return;
    }
    setIsSavingToken(true);
    try {
      const res = await fetch("/api/settings/hf-token", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.detail ?? data?.error ?? "Failed to save token");
      }
      setConfigured(Boolean(data?.configured));
      setToken("");
      toast.success("Hugging Face token saved");
    } catch (err) {
      toast.error("Could not save token", {
        description: err instanceof Error ? err.message : "The backend may be unreachable.",
      });
    } finally {
      setIsSavingToken(false);
    }
  }, [token]);

  const handleClearToken = useCallback(async () => {
    setIsSavingToken(true);
    try {
      const res = await fetch("/api/settings/hf-token", { method: "DELETE" });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.detail ?? data?.error ?? "Failed to clear token");
      }
      setConfigured(Boolean(data?.configured));
      toast.success("Hugging Face token cleared");
    } catch (err) {
      toast.error("Could not clear token", {
        description: err instanceof Error ? err.message : "The backend may be unreachable.",
      });
    } finally {
      setIsSavingToken(false);
    }
  }, []);

  const handleSaveInference = useCallback(async () => {
    if (isNaN(maxNumToken) || maxNumToken < 512 || maxNumToken > 131072) {
      toast.error("Invalid token count", {
        description: "Max tokens must be a number between 512 and 131,072.",
      });
      return;
    }

    setIsSavingInference(true);
    try {
      const res = await fetch("/api/settings/inference", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          litert_backend: litertBackend,
          max_num_token: Number(maxNumToken),
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.detail ?? data?.error ?? "Failed to save inference settings");
      }
      setLitertBackend(data.litert_backend);
      setMaxNumToken(data.max_num_token);
      toast.success("Inference settings saved", {
        description: `Backend set to ${data.litert_backend.toUpperCase()} with ${Number(data.max_num_token).toLocaleString()} tokens.`,
      });
    } catch (err) {
      toast.error("Could not save inference settings", {
        description: err instanceof Error ? err.message : "The backend may be unreachable.",
      });
    } finally {
      setIsSavingInference(false);
    }
  }, [litertBackend, maxNumToken]);

  const handleApplyRecommendation = useCallback(() => {
    if (!systemResources) return;
    setLitertBackend(systemResources.recommended_backend);
    setMaxNumToken(systemResources.recommended_max_num_tokens);
    toast.info("Applied recommended values", {
      description: `Backend: ${systemResources.recommended_backend.toUpperCase()}, Tokens: ${systemResources.recommended_max_num_tokens.toLocaleString()}. Click Save to persist.`,
    });
  }, [systemResources]);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 p-4 md:p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground text-sm">
          Configure hardware execution, context capacity, and credentials used by Buddhi AI Studio.
        </p>
      </div>

      {/* System Resource Recommendation Alert */}
      {systemResources && (
        <Alert>
          <CpuIcon />
          <AlertTitle className="flex items-center gap-2">
            System Resource Analysis
            <Badge variant="outline" className="text-xs font-normal">
              {systemResources.recommended_backend.toUpperCase()} Recommended
            </Badge>
          </AlertTitle>
          <AlertDescription>
            {systemResources.reasoning}
          </AlertDescription>
          <AlertAction>
            <Button
              size="xs"
              variant="outline"
              onClick={handleApplyRecommendation}
            >
              <SparklesIcon className="size-3.5 mr-1" />
              Apply Recommendation
            </Button>
          </AlertAction>
        </Alert>
      )}

      {/* Inference Settings Card */}
      {isLoading ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-4 w-64" />
          </CardHeader>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Inference Configuration</CardTitle>
            <CardDescription>
              Configure the LiteRT runtime execution backend and maximum context window for Gemma 4 models.
            </CardDescription>
            <CardAction>
              <Badge variant="secondary" className="font-mono text-xs">
                {litertBackend.toUpperCase()} • {Number(maxNumToken).toLocaleString()} tokens
              </Badge>
            </CardAction>
          </CardHeader>

          <CardContent className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Execution Backend</label>
              <Select
                value={litertBackend}
                onValueChange={(val) => val && setLitertBackend(val)}
              >
                <SelectTrigger className="w-full sm:w-80">
                  <SelectValue placeholder="Select backend" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="cpu">
                    <div className="flex items-center gap-2">
                      <span>CPU</span>
                      <span className="text-muted-foreground text-xs">(Standard)</span>
                    </div>
                  </SelectItem>
                  <SelectItem
                    value="gpu"
                    disabled={
                      systemResources?.supported_backends.find((b) => b.id === "gpu")?.supported === false
                    }
                  >
                    <div className="flex items-center gap-2">
                      <span>GPU</span>
                      {systemResources?.recommended_backend === "gpu" && (
                        <span className="text-primary text-xs font-medium">• Recommended</span>
                      )}
                      {systemResources?.gpu_name && (
                        <span className="text-muted-foreground text-xs">({systemResources.gpu_name})</span>
                      )}
                    </div>
                  </SelectItem>
                  <SelectItem
                    value="npu"
                    disabled={
                      systemResources?.supported_backends.find((b) => b.id === "npu")?.supported === false
                    }
                  >
                    <div className="flex items-center gap-2">
                      <span>NPU</span>
                      {systemResources?.supported_backends.find((b) => b.id === "npu")?.supported === false && (
                        <span className="text-muted-foreground text-xs">(Requires OpenVINO)</span>
                      )}
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-muted-foreground text-xs">
                LiteRT dynamically re-arms without restarting the backend service. Falls back safely to CPU if accelerator delegate fails.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">Max Number of Tokens (`max_num_token`)</label>
                <span className="text-muted-foreground text-xs font-mono">
                  Default: 16,384
                </span>
              </div>
              <Input
                type="number"
                min={512}
                max={131072}
                step={1024}
                value={maxNumToken}
                onChange={(e) => setMaxNumToken(parseInt(e.target.value, 10) || 0)}
                className="w-full sm:w-80 font-mono"
              />
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-muted-foreground text-xs mr-1">Presets:</span>
                {TOKEN_PRESETS.map((preset) => (
                  <Button
                    key={preset}
                    size="sm"
                    variant={maxNumToken === preset ? "default" : "outline"}
                    className="h-6 px-2 text-xs font-mono"
                    onClick={() => setMaxNumToken(preset)}
                  >
                    {preset >= 1024 ? `${preset / 1024}k` : preset}
                  </Button>
                ))}
              </div>
              <p className="text-muted-foreground text-xs">
                Controls the maximum sequence length allocated for model KV cache memory in RAM/VRAM.
              </p>
            </div>
          </CardContent>

          <CardFooter className="gap-2">
            <Button
              disabled={isSavingInference}
              onClick={() => void handleSaveInference()}
            >
              {isSavingInference ? (
                <>
                  <Loader2Icon className="size-4 animate-spin mr-1.5" />
                  Saving...
                </>
              ) : (
                "Save Configuration"
              )}
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* Hugging Face Token Card */}
      {isLoading ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-4 w-64" />
          </CardHeader>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <KeyIcon className="size-4 text-muted-foreground" />
              Hugging Face Token
            </CardTitle>
            <CardDescription>
              Required to download gated models (e.g. EmbeddingGemma) from Hugging Face.
            </CardDescription>
            <CardAction>
              <Badge variant={configured ? "default" : "secondary"}>
                {configured ? "Configured" : "Not configured"}
              </Badge>
            </CardAction>
          </CardHeader>
          {configured ? (
            <>
              <CardContent>
                <p className="text-muted-foreground text-sm">
                  A Hugging Face token is configured and active.
                </p>
              </CardContent>
              <CardFooter className="gap-2">
                <Button disabled={isSavingToken} onClick={() => void handleClearToken()} variant="outline">
                  Clear Token
                </Button>
              </CardFooter>
            </>
          ) : (
            <>
              <CardContent>
                <Input
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="hf_..."
                  type="password"
                  value={token}
                />
              </CardContent>
              <CardFooter className="gap-2">
                <Button disabled={isSavingToken} onClick={() => void handleSaveToken()}>
                  Save Token
                </Button>
              </CardFooter>
            </>
          )}
        </Card>
      )}
    </div>
  );
}
