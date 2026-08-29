"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  useModelCatalog,
  type DownloadStatus,
  type ModelCatalogEntry,
} from "@/hooks/use-model-catalog";
import { useEmbeddingModelStatus } from "@/hooks/use-embedding-model-status";
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  DownloadIcon,
  KeyIcon,
  Loader2Icon,
  PauseIcon,
  PlayIcon,
  XIcon,
} from "lucide-react";

function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value.toFixed(exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

const STATUS_LABEL: Record<DownloadStatus, string> = {
  idle: "Not downloaded",
  downloading: "Downloading",
  paused: "Paused",
  completed: "Downloaded",
  failed: "Failed",
};

const STATUS_VARIANT: Record<DownloadStatus, "default" | "secondary" | "destructive" | "outline"> = {
  idle: "secondary",
  downloading: "default",
  paused: "outline",
  completed: "default",
  failed: "destructive",
};

function useHfTokenStatus() {
  const [configured, setConfigured] = useState<boolean | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/settings/hf-token");
      const data = await res.json();
      setConfigured(Boolean(data.configured));
    } catch (err) {
      console.error("[downloads] failed to load HF token status:", err);
      setConfigured(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/api/settings/hf-token");
        const data = await res.json();
        if (!cancelled) setConfigured(Boolean(data.configured));
      } catch (err) {
        console.error("[downloads] failed to load HF token status:", err);
        if (!cancelled) setConfigured(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { configured, refresh };
}

function ModelCard({
  entry,
  tokenConfigured,
  state,
  onStart,
  onPause,
  onResume,
  onCancel,
}: {
  entry: ModelCatalogEntry;
  tokenConfigured: boolean;
  state: {
    status: DownloadStatus;
    downloaded_bytes: number;
    total_bytes: number | null;
    percentage: number;
    error: string | null;
  } | undefined;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
}) {
  const status = state?.status ?? "idle";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{entry.name}</CardTitle>
        <CardDescription className="font-mono">{entry.repo_id}</CardDescription>
        <CardAction>
          <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABEL[status]}</Badge>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {status === "completed" ? (
          <div className="text-muted-foreground flex items-center gap-2 text-sm">
            <CheckCircle2Icon className="text-primary size-4" />
            Model downloaded and ready
            {state?.total_bytes != null && ` (${formatBytes(state.total_bytes)})`}
          </div>
        ) : (
          <Progress value={state?.total_bytes ? state.percentage : null}>
            <div className="flex w-full items-center justify-between">
              <ProgressLabel>
                {formatBytes(state?.downloaded_bytes)}
                {state?.total_bytes ? ` / ${formatBytes(state.total_bytes)}` : ""}
              </ProgressLabel>
              <ProgressValue />
            </div>
          </Progress>
        )}

        {status === "failed" && state?.error && (
          <Alert variant="destructive">
            <AlertTriangleIcon />
            <AlertTitle>Download failed</AlertTitle>
            <AlertDescription>{state.error}</AlertDescription>
          </Alert>
        )}
      </CardContent>

      <CardFooter className="gap-2">
        {(status === "idle" || status === "failed") && (
          <Button disabled={!tokenConfigured} onClick={onStart}>
            <DownloadIcon />
            Download
          </Button>
        )}
        {status === "downloading" && (
          <Button variant="outline" onClick={onPause}>
            <PauseIcon />
            Pause
          </Button>
        )}
        {status === "paused" && (
          <>
            <Button onClick={onResume}>
              <PlayIcon />
              Resume
            </Button>
            <Button variant="outline" onClick={onCancel}>
              <XIcon />
              Cancel
            </Button>
          </>
        )}
      </CardFooter>
    </Card>
  );
}

const EMBEDDING_STATUS_LABEL: Record<
  ReturnType<typeof useEmbeddingModelStatus>["status"],
  string
> = {
  not_downloaded: "Not downloaded",
  downloading: "Downloading",
  paused: "Paused",
  ready: "Downloaded",
  error: "Failed",
};

const EMBEDDING_STATUS_VARIANT: Record<
  ReturnType<typeof useEmbeddingModelStatus>["status"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  not_downloaded: "secondary",
  downloading: "default",
  paused: "outline",
  ready: "default",
  error: "destructive",
};

function getEmbeddingPhaseDescription(
  currentPhase: string | null,
  files?: ReturnType<typeof useEmbeddingModelStatus>["files"]
): string {
  if (currentPhase === "model") {
    const modelState = files?.["embeddinggemma-300m-litert"];
    if (modelState && modelState.downloaded_bytes > 0 && modelState.total_bytes) {
      return `Downloading LiteRT model weights (Phase 1/2: ${formatBytes(modelState.downloaded_bytes)} / ${formatBytes(modelState.total_bytes)})`;
    }
    return "Downloading LiteRT model weights (Phase 1/2)...";
  }
  if (currentPhase === "tokenizer") {
    const tokState = files?.["embeddinggemma-300m-tokenizer"];
    if (tokState && tokState.downloaded_bytes > 0 && tokState.total_bytes) {
      return `Downloading SentencePiece tokenizer (Phase 2/2: ${formatBytes(tokState.downloaded_bytes)} / ${formatBytes(tokState.total_bytes)})`;
    }
    return "Downloading SentencePiece tokenizer (Phase 2/2)...";
  }
  if (currentPhase === "loading") {
    return "Initializing LiteRT interpreter and tokenizer...";
  }
  return "Downloading model files...";
}

function EmbeddingModelCard({ tokenConfigured }: { tokenConfigured: boolean }) {
  const {
    modelId,
    repoId,
    status,
    error,
    downloadedBytes,
    totalBytes,
    percentage,
    currentPhase,
    files,
    startDownload,
    pauseDownload,
    resumeDownload,
    cancelDownload,
  } = useEmbeddingModelStatus();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{modelId ?? "EmbeddingGemma 300M"}</CardTitle>
        <CardDescription className="font-mono">
          {repoId ?? "litert-community/embeddinggemma-300m"}
        </CardDescription>
        <CardAction>
          <Badge variant={EMBEDDING_STATUS_VARIANT[status]}>
            {EMBEDDING_STATUS_LABEL[status]}
          </Badge>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {status === "ready" && (
          <div className="text-muted-foreground flex items-center gap-2 text-sm">
            <CheckCircle2Icon className="text-primary size-4" />
            Model downloaded and ready
            {totalBytes ? ` (${formatBytes(totalBytes)})` : ""}
          </div>
        )}

        {(status === "downloading" || status === "paused") && (
          <div className="flex flex-col gap-2">
            <div className="text-muted-foreground flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 font-medium">
                {status === "downloading" && (
                  <Loader2Icon className="size-3.5 animate-spin" />
                )}
                {getEmbeddingPhaseDescription(currentPhase, files)}
              </span>
              <span>{percentage.toFixed(1)}%</span>
            </div>
            <Progress value={totalBytes ? percentage : null}>
              <div className="flex w-full items-center justify-between">
                <ProgressLabel>
                  {formatBytes(downloadedBytes)}
                  {totalBytes ? ` / ${formatBytes(totalBytes)}` : ""}
                </ProgressLabel>
                <ProgressValue />
              </div>
            </Progress>
          </div>
        )}

        {status === "not_downloaded" && (
          <div className="text-muted-foreground text-sm">
            Includes LiteRT model weights and SentencePiece tokenizer (~194.8 MB total).
          </div>
        )}

        {status === "error" && error && (
          <Alert variant="destructive">
            <AlertTriangleIcon />
            <AlertTitle>Download failed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </CardContent>

      <CardFooter className="gap-2">
        {(status === "not_downloaded" || status === "error") && (
          <Button disabled={!tokenConfigured} onClick={() => void startDownload()}>
            <DownloadIcon />
            Download
          </Button>
        )}
        {status === "downloading" && (
          <Button variant="outline" onClick={() => void pauseDownload()}>
            <PauseIcon />
            Pause
          </Button>
        )}
        {status === "paused" && (
          <>
            <Button onClick={() => void resumeDownload()}>
              <PlayIcon />
              Resume
            </Button>
            <Button variant="outline" onClick={() => void cancelDownload()}>
              <XIcon />
              Cancel
            </Button>
          </>
        )}
      </CardFooter>
    </Card>
  );
}

export default function DownloadsPage() {
  const { catalog, states, isLoading, error, start, pause, resume, cancel } = useModelCatalog();
  const { configured: tokenConfigured } = useHfTokenStatus();

  const llmModels = catalog.filter((m) => m.category === "llm");

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 p-4 md:p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Model Download</h1>
        <p className="text-muted-foreground text-sm">
          Download on-device models used by Buddhi AI Studio.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangleIcon />
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {tokenConfigured === false && (
        <Alert>
          <KeyIcon />
          <AlertTitle>Hugging Face token required</AlertTitle>
          <AlertDescription>
            Some models (like EmbeddingGemma) require an accepted-license Hugging Face token to
            download.{" "}
            <Link href="/settings" className="underline">
              Configure it on the Settings page
            </Link>{" "}
            before downloading.
          </AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-4 w-64" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-2 w-full" />
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="llm">
          <TabsList>
            <TabsTrigger value="llm">LLM</TabsTrigger>
            <TabsTrigger value="embedding">Embeddings</TabsTrigger>
          </TabsList>
          <TabsContent value="llm" className="flex flex-col gap-4">
            {llmModels.map((entry) => (
              <ModelCard
                key={entry.id}
                entry={entry}
                tokenConfigured={tokenConfigured ?? false}
                state={states[entry.id]}
                onStart={() => void start(entry.id)}
                onPause={() => void pause(entry.id)}
                onResume={() => void resume(entry.id)}
                onCancel={() => void cancel(entry.id)}
              />
            ))}
          </TabsContent>
          <TabsContent value="embedding" className="flex flex-col gap-4">
            <EmbeddingModelCard tokenConfigured={tokenConfigured ?? false} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
