"use client";

import * as React from "react";
import Link from "next/link";
import {
  BoxIcon,
  ClockIcon,
  DatabaseIcon,
  FolderOpenIcon,
  HammerIcon,
  LayoutGridIcon,
  ListIcon,
  PlusIcon,
  SearchIcon,
  Trash2Icon,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { CreateProjectDialog } from "@/components/build/create-project-dialog";
import { cn } from "@/lib/utils";

export interface BuildProjectSummary {
  id: string;
  name: string;
  description: string;
  template: "nextjs-vibe" | "python-blank" | "node-blank";
  db_dialect: "postgresql" | "sqlite";
  active_session_id: string | null;
  session_active: boolean;
  runtime_image: string;
  created_at: string;
  updated_at: string;
}

const TEMPLATE_LABELS: Record<BuildProjectSummary["template"], string> = {
  "nextjs-vibe": "Next.js 16+",
  "python-blank": "Python",
  "node-blank": "Node.js",
};

function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function BuildDashboard() {
  const [projects, setProjects] = React.useState<BuildProjectSummary[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [viewMode, setViewMode] = React.useState<"grid" | "list">("grid");
  const [createOpen, setCreateOpen] = React.useState(false);

  React.useEffect(() => {
    let active = true;
    try {
      const saved = window.localStorage.getItem("buddhi:build:view-mode");
      if (saved === "grid" || saved === "list") {
        queueMicrotask(() => {
          if (active) setViewMode(saved);
        });
      }
    } catch {
      // ignore storage errors
    }
    return () => {
      active = false;
    };
  }, []);

  const handleViewChange = React.useCallback((mode: "grid" | "list") => {
    setViewMode(mode);
    try {
      window.localStorage.setItem("buddhi:build:view-mode", mode);
    } catch {
      // ignore
    }
  }, []);

  const fetchProjects = React.useCallback(async () => {
    try {
      const res = await fetch("/api/build/projects");
      if (res.ok) {
        const data = await res.json();
        setProjects(Array.isArray(data) ? data : []);
      } else {
        setProjects([]);
      }
    } catch {
      setProjects([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) void fetchProjects();
    });
    return () => {
      active = false;
    };
  }, [fetchProjects]);

  const handleDelete = async (e: React.MouseEvent, project: BuildProjectSummary) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      const res = await fetch(`/api/build/projects/${encodeURIComponent(project.id)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setProjects((prev) => prev.filter((p) => p.id !== project.id));
        toast.success(`Deleted "${project.name}"`);
      } else {
        toast.error("Failed to delete project");
      }
    } catch {
      toast.error("Failed to delete project");
    }
  };

  const filtered = React.useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.template.toLowerCase().includes(q)
    );
  }, [projects, searchQuery]);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <HammerIcon className="size-5 text-primary" aria-hidden="true" />
            <h1 className="text-2xl font-semibold tracking-tight">Build</h1>
          </div>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Create and resume AI-assisted software projects inside isolated OpenSandbox containers.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <CreateProjectDialog open={createOpen} onOpenChange={setCreateOpen} />
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative w-full max-w-sm">
          <SearchIcon
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            placeholder="Search projects..."
            aria-label="Search projects"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8"
          />
        </div>

        <div
          role="group"
          aria-label="Project view layout"
          className="inline-flex items-center rounded-md border border-border bg-card p-0.5"
        >
          <Button
            type="button"
            variant={viewMode === "grid" ? "secondary" : "ghost"}
            size="sm"
            aria-label="Grid view"
            aria-pressed={viewMode === "grid"}
            onClick={() => handleViewChange("grid")}
            className="h-7 gap-1.5 px-2.5 text-xs"
          >
            <LayoutGridIcon className="size-3.5" aria-hidden="true" />
            <span>Grid</span>
          </Button>
          <Button
            type="button"
            variant={viewMode === "list" ? "secondary" : "ghost"}
            size="sm"
            aria-label="List view"
            aria-pressed={viewMode === "list"}
            onClick={() => handleViewChange("list")}
            className="h-7 gap-1.5 px-2.5 text-xs"
          >
            <ListIcon className="size-3.5" aria-hidden="true" />
            <span>List</span>
          </Button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, idx) => (
            <Skeleton key={idx} className="h-40 rounded-lg" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card/50 px-6 py-16 text-center">
          <FolderOpenIcon className="mb-3 size-10 text-muted-foreground/60" aria-hidden="true" />
          <h2 className="text-base font-medium">
            {projects.length === 0 ? "No projects yet" : "No matching projects"}
          </h2>
          <p className="mt-1 max-w-md text-sm text-muted-foreground">
            {projects.length === 0
              ? "Create your first project to launch an OpenSandbox workspace and start building with BuddhiAI."
              : "Try adjusting your search query or create a new project."}
          </p>
          {projects.length === 0 && (
            <Button
              type="button"
              className="mt-4 gap-1.5"
              onClick={() => setCreateOpen(true)}
            >
              <PlusIcon className="size-4" aria-hidden="true" />
              <span>Create New</span>
            </Button>
          )}
        </div>
      ) : viewMode === "grid" ? (
        <div
          data-testid="projects-grid"
          className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
        >
          {filtered.map((project) => (
            <Link
              key={project.id}
              href={`/build/project/${encodeURIComponent(project.id)}`}
              className="group block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <Card className="flex h-full flex-col border-border transition-colors group-hover:border-primary/50">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="line-clamp-1 text-base font-semibold">
                      {project.name}
                    </CardTitle>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Delete ${project.name}`}
                      onClick={(e) => void handleDelete(e, project)}
                      className="size-7 shrink-0 text-muted-foreground hover:text-destructive"
                    >
                      <Trash2Icon className="size-3.5" aria-hidden="true" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 pb-3">
                  <p className="line-clamp-2 text-xs text-muted-foreground">
                    {project.description || "No description provided."}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    <Badge variant="secondary" className="text-[11px]">
                      {TEMPLATE_LABELS[project.template] || project.template}
                    </Badge>
                    <Badge variant="outline" className="gap-1 text-[11px]">
                      <DatabaseIcon className="size-3" aria-hidden="true" />
                      <span>{project.db_dialect}</span>
                    </Badge>
                  </div>
                </CardContent>
                <CardFooter className="flex items-center justify-between border-t border-border/60 pt-2.5 text-[11px] text-muted-foreground">
                  <span className="inline-flex items-center gap-1 font-mono tabular-nums">
                    <ClockIcon className="size-3" aria-hidden="true" />
                    {formatRelativeTime(project.updated_at)}
                  </span>
                  <Badge
                    variant="outline"
                    className={cn(
                      "gap-1 text-[10px]",
                      project.session_active
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                        : "text-muted-foreground"
                    )}
                  >
                    <BoxIcon className="size-2.5" aria-hidden="true" />
                    <span>{project.session_active ? "Running" : "Stopped"}</span>
                  </Badge>
                </CardFooter>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        <div
          data-testid="projects-list"
          className="overflow-hidden rounded-lg border border-border bg-card"
        >
          <div className="divide-y divide-border">
            {filtered.map((project) => (
              <Link
                key={project.id}
                href={`/build/project/${encodeURIComponent(project.id)}`}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">{project.name}</span>
                    <Badge variant="secondary" className="text-[11px]">
                      {TEMPLATE_LABELS[project.template] || project.template}
                    </Badge>
                    <Badge variant="outline" className="text-[11px]">
                      {project.db_dialect}
                    </Badge>
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">
                    {project.description || "No description provided."}
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                    {formatRelativeTime(project.updated_at)}
                  </span>
                  <Badge
                    variant="outline"
                    className={cn(
                      "gap-1 text-[10px]",
                      project.session_active
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                        : "text-muted-foreground"
                    )}
                  >
                    <BoxIcon className="size-2.5" aria-hidden="true" />
                    <span>{project.session_active ? "Running" : "Stopped"}</span>
                  </Badge>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Delete ${project.name}`}
                    onClick={(e) => void handleDelete(e, project)}
                    className="size-7 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2Icon className="size-3.5" aria-hidden="true" />
                  </Button>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
