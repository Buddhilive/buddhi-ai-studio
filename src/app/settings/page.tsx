"use client";

import { useCallback, useEffect, useState } from "react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

export default function SettingsPage() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [token, setToken] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const refreshStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/settings/hf-token");
      const data = await res.json();
      setConfigured(Boolean(data.configured));
    } catch (err) {
      console.error("[settings] failed to load HF token status:", err);
      toast.error("Could not load settings", {
        description: err instanceof Error ? err.message : "The backend may be unreachable.",
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  const handleSave = useCallback(async () => {
    if (!token.trim()) {
      toast.error("Enter a token before saving");
      return;
    }
    setIsSaving(true);
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
      setIsSaving(false);
    }
  }, [token]);

  const handleClear = useCallback(async () => {
    setIsSaving(true);
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
      setIsSaving(false);
    }
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 p-4 md:p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground text-sm">
          Configure credentials used by Buddhi AI Studio.
        </p>
      </div>

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
            <CardTitle className="text-base">Hugging Face Token</CardTitle>
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
                  A Hugging Face token is configured.
                </p>
              </CardContent>
              <CardFooter className="gap-2">
                <Button disabled={isSaving} onClick={() => void handleClear()} variant="outline">
                  Clear
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
                <Button disabled={isSaving} onClick={() => void handleSave()}>
                  Save
                </Button>
              </CardFooter>
            </>
          )}
        </Card>
      )}
    </div>
  );
}
