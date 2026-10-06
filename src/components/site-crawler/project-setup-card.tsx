"use client";

import * as React from "react";
import { FolderPlusIcon, DatabaseIcon, PlusIcon } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { BucketInfo } from "@/lib/site-crawler/types";

function slugify(name: string): string {
  const cleaned = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return cleaned ? cleaned.slice(0, 64) : "project";
}

export function ProjectSetupCard({
  projectName,
  onProjectNameChange,
  bucket,
  onBucketChange,
  buckets,
  onBucketCreated,
  disabled = false,
}: {
  projectName: string;
  onProjectNameChange: (val: string) => void;
  bucket: string;
  onBucketChange: (val: string) => void;
  buckets: BucketInfo[];
  onBucketCreated: (newBucket: string) => void;
  disabled?: boolean;
}) {
  const [isDialogOpen, setIsDialogOpen] = React.useState(false);
  const [newBucketName, setNewBucketName] = React.useState("");
  const [isCreatingBucket, setIsCreatingBucket] = React.useState(false);
  const [bucketError, setBucketError] = React.useState<string | null>(null);

  const slug = slugify(projectName);

  const handleCreateBucket = async () => {
    if (!newBucketName.trim()) return;
    setIsCreatingBucket(true);
    setBucketError(null);

    try {
      const res = await fetch("/api/storage/buckets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newBucketName.trim().toLowerCase() }),
      });

      const data = await res.json();
      if (!res.ok) {
        setBucketError(data.error?.message || data.detail || "Failed to create bucket");
      } else {
        onBucketCreated(data.name);
        onBucketChange(data.name);
        setNewBucketName("");
        setIsDialogOpen(false);
      }
    } catch (err: unknown) {
      setBucketError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsCreatingBucket(false);
    }
  };

  return (
    <Card className="border-border/60">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <FolderPlusIcon className="h-4 w-4 text-primary" />
          <CardTitle className="text-base">1. Project & Storage</CardTitle>
        </div>
        <CardDescription>
          Specify your project name and destination RustFS storage bucket.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Project Name */}
          <div className="space-y-1.5">
            <Label htmlFor="projectName" className="text-xs font-medium">
              Project Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="projectName"
              placeholder="e.g. Documentation Scraper"
              value={projectName}
              onChange={(e) => onProjectNameChange(e.target.value)}
              disabled={disabled}
              maxLength={100}
            />
            <p className="text-[11px] text-muted-foreground">
              Storage folder slug:{" "}
              <code className="px-1 py-0.5 rounded bg-muted font-mono text-[11px] text-foreground">
                {slug}/
              </code>
            </p>
          </div>

          {/* Bucket Selection */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="bucketSelect" className="text-xs font-medium">
                Storage Bucket <span className="text-destructive">*</span>
              </Label>
              <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  className="h-6 gap-1 text-[11px] px-2"
                  disabled={disabled}
                  onClick={() => setIsDialogOpen(true)}
                >
                  <PlusIcon className="h-3 w-3" />
                  New Bucket
                </Button>
                <DialogContent className="sm:max-w-md">
                  <DialogHeader>
                    <DialogTitle>Create Storage Bucket</DialogTitle>
                    <DialogDescription>
                      Create a new S3-compatible bucket in RustFS for organizing your crawler outputs.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-2 py-2">
                    <Label htmlFor="newBucketInput" className="text-xs">
                      Bucket Name (lowercase, numbers, hyphens)
                    </Label>
                    <Input
                      id="newBucketInput"
                      placeholder="e.g. web-crawls"
                      value={newBucketName}
                      onChange={(e) => setNewBucketName(e.target.value)}
                    />
                    {bucketError && <p className="text-xs text-destructive">{bucketError}</p>}
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleCreateBucket} disabled={isCreatingBucket || !newBucketName.trim()}>
                      {isCreatingBucket ? "Creating..." : "Create"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>

            <Select
              value={bucket}
              onValueChange={(val: string | null) => {
                if (val) onBucketChange(val);
              }}
              disabled={disabled}
            >
              <SelectTrigger id="bucketSelect" className="w-full">
                <SelectValue placeholder="Select bucket" />
              </SelectTrigger>
              <SelectContent>
                {buckets.map((b) => (
                  <SelectItem key={b.name} value={b.name}>
                    <div className="flex items-center gap-2">
                      <DatabaseIcon className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>{b.name}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-[11px] text-muted-foreground">
              Files are saved under <span className="font-mono">{bucket}/{slug}/</span>
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
