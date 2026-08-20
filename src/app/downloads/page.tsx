"use client";

import { useModelDownload, type DownloadStatus } from "@/hooks/use-model-download";
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
import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  DownloadIcon,
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

export default function DownloadsPage() {
  const { state, availability, isLoading, error, start, pause, resume, cancel } = useModelDownload();

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 p-4 md:p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Model Download</h1>
        <p className="text-muted-foreground text-sm">
          Download the on-device model used by Buddhi AI Studio.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangleIcon />
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading || !state ? (
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
        <Card>
          <CardHeader>
            <CardTitle className="font-mono text-base">{state.filename}</CardTitle>
            <CardDescription>{state.repo_id}</CardDescription>
            <CardAction>
              <Badge variant={STATUS_VARIANT[state.status]}>{STATUS_LABEL[state.status]}</Badge>
            </CardAction>
          </CardHeader>

          <CardContent className="flex flex-col gap-4">
            {state.status === "completed" ? (
              <div className="text-muted-foreground flex items-center gap-2 text-sm">
                <CheckCircle2Icon className="text-primary size-4" />
                Model downloaded and ready
                {availability?.size_bytes != null && ` (${formatBytes(availability.size_bytes)})`}
              </div>
            ) : (
              <Progress value={state.total_bytes ? state.percentage : null}>
                <div className="flex w-full items-center justify-between">
                  <ProgressLabel>
                    {formatBytes(state.downloaded_bytes)}
                    {state.total_bytes ? ` / ${formatBytes(state.total_bytes)}` : ""}
                  </ProgressLabel>
                  <ProgressValue />
                </div>
              </Progress>
            )}

            {state.status === "failed" && state.error && (
              <Alert variant="destructive">
                <AlertTriangleIcon />
                <AlertTitle>Download failed</AlertTitle>
                <AlertDescription>{state.error}</AlertDescription>
              </Alert>
            )}
          </CardContent>

          <CardFooter className="gap-2">
            {(state.status === "idle" || state.status === "failed") && (
              <Button onClick={() => void start()}>
                <DownloadIcon />
                Download
              </Button>
            )}
            {state.status === "downloading" && (
              <Button variant="outline" onClick={() => void pause()}>
                <PauseIcon />
                Pause
              </Button>
            )}
            {state.status === "paused" && (
              <>
                <Button onClick={() => void resume()}>
                  <PlayIcon />
                  Resume
                </Button>
                <Button variant="outline" onClick={() => void cancel()}>
                  <XIcon />
                  Cancel
                </Button>
              </>
            )}
          </CardFooter>
        </Card>
      )}
    </div>
  );
}
