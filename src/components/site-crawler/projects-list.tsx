"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArchiveIcon,
  CheckCircle2Icon,
  DownloadIcon,
  ExternalLinkIcon,
  FileJsonIcon,
  Loader2Icon,
  RotateCwIcon,
  StopCircleIcon,
  Trash2Icon,
  XCircleIcon,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { ProjectSummary } from "@/lib/site-crawler/types";

export function ProjectsList({ bucket }: { bucket: string }) {
  const [projects, setProjects] = React.useState<ProjectSummary[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const fetchProjects = React.useCallback(async () => {
    if (!bucket) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/tools/site-crawler/projects?bucket=${encodeURIComponent(bucket)}`);
      if (res.ok) {
        const data = await res.json();
        setProjects(data || []);
      } else {
        const err = await res.json();
        setError(err.error?.message || err.detail || "Failed to load projects");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsLoading(false);
    }
  }, [bucket]);

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchProjects();
  }, [fetchProjects]);

  const handleDelete = async (slug: string) => {
    try {
      const res = await fetch(
        `/api/tools/site-crawler/projects/${slug}?bucket=${encodeURIComponent(bucket)}`,
        { method: "DELETE" }
      );
      if (res.ok) {
        setProjects((curr) => curr.filter((p) => p.slug !== slug));
      } else {
        const err = await res.json();
        alert(err.error?.message || err.detail || "Failed to delete project");
      }
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : String(e));
    }
  };

  const renderStatus = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <Badge variant="outline" className="text-[11px] gap-1 border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10">
            <CheckCircle2Icon className="h-3 w-3" />
            Completed
          </Badge>
        );
      case "running":
        return (
          <Badge variant="outline" className="text-[11px] gap-1 border-blue-500/30 text-blue-600 dark:text-blue-400 bg-blue-500/10">
            <Loader2Icon className="h-3 w-3 animate-spin" />
            Running
          </Badge>
        );
      case "cancelled":
        return (
          <Badge variant="outline" className="text-[11px] gap-1 border-amber-500/30 text-amber-600 dark:text-amber-400 bg-amber-500/10">
            <StopCircleIcon className="h-3 w-3" />
            Cancelled
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="text-[11px] gap-1 border-destructive/30 text-destructive bg-destructive/10">
            <XCircleIcon className="h-3 w-3" />
            {status}
          </Badge>
        );
    }
  };

  return (
    <Card className="border-border/60">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">Saved Crawler Projects</CardTitle>
            <CardDescription>
              Browse completed and ongoing projects in bucket <span className="font-mono">{bucket}</span>.
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="xs"
            className="h-7 text-xs gap-1.5 self-start sm:self-auto"
            onClick={fetchProjects}
            disabled={isLoading}
          >
            <RotateCwIcon className={`h-3 w-3 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="p-3 mb-4 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs">
            {error}
          </div>
        )}

        {projects.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground text-xs">
            {isLoading ? "Loading projects..." : `No projects found in bucket "${bucket}". Start a new run to create one.`}
          </div>
        ) : (
          <div className="rounded-md border border-border/60 overflow-hidden">
            <Table>
              <TableHeader className="bg-muted/50">
                <TableRow>
                  <TableHead className="text-xs font-semibold">Project Name</TableHead>
                  <TableHead className="text-xs font-semibold">Status</TableHead>
                  <TableHead className="text-xs font-semibold">Pages</TableHead>
                  <TableHead className="text-xs font-semibold">Records</TableHead>
                  <TableHead className="text-xs font-semibold">Created</TableHead>
                  <TableHead className="text-xs font-semibold text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projects.map((proj) => (
                  <TableRow key={proj.slug} className="hover:bg-muted/30">
                    <TableCell className="font-medium text-xs">
                      <Link
                        href={`/tools/site-crawler/projects/${proj.slug}?bucket=${encodeURIComponent(bucket)}`}
                        className="hover:underline flex items-center gap-1.5 text-foreground"
                      >
                        <span>{proj.name}</span>
                        <ExternalLinkIcon className="h-3 w-3 text-muted-foreground" />
                      </Link>
                      <div className="text-[10px] text-muted-foreground font-mono">{proj.slug}</div>
                    </TableCell>
                    <TableCell>{renderStatus(proj.status)}</TableCell>
                    <TableCell className="text-xs font-mono">
                      {proj.counts.extracted} / {proj.counts.total}
                    </TableCell>
                    <TableCell className="text-xs font-mono">{proj.counts.records}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(proj.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        {/* Download JSON */}
                        <a
                          href={`/api/tools/site-crawler/projects/${proj.slug}/data?bucket=${encodeURIComponent(bucket)}`}
                          download
                          title="Download data.json"
                        >
                          <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground">
                            <FileJsonIcon className="h-3.5 w-3.5" />
                          </Button>
                        </a>

                        {/* Download ZIP */}
                        <a
                          href={`/api/tools/site-crawler/projects/${proj.slug}/zip?bucket=${encodeURIComponent(bucket)}`}
                          download
                          title="Download complete project ZIP"
                        >
                          <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground">
                            <ArchiveIcon className="h-3.5 w-3.5" />
                          </Button>
                        </a>

                        {/* Delete confirmation dialog */}
                        <AlertDialog>
                          <AlertDialogTrigger
                            render={
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                                disabled={proj.status === "running"}
                                title="Delete project"
                              >
                                <Trash2Icon className="h-3.5 w-3.5" />
                              </Button>
                            }
                          />
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete Project &quot;{proj.name}&quot;?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This will permanently remove all files, raw scraped markdown, and extracted
                                records from <code className="font-mono text-xs">{bucket}/{proj.slug}/</code> in RustFS.
                                This action cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => handleDelete(proj.slug)}
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              >
                                Delete Project
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
