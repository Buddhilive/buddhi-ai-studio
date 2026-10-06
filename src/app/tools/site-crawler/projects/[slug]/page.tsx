"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  ArchiveIcon,
  ArrowLeftIcon,
  CheckCircle2Icon,
  ClockIcon,
  DownloadIcon,
  FileCodeIcon,
  FileJsonIcon,
  FileTextIcon,
  LayersIcon,
  Loader2Icon,
  RotateCwIcon,
  SparklesIcon,
  StopCircleIcon,
  XCircleIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { ResultsTable } from "@/components/site-crawler/results-table";
import { MarkdownViewer } from "@/components/crawler/markdown-viewer";
import {
  JobStatusType,
  PageDetailResponse,
  PageResult,
  ProjectDetail,
} from "@/lib/site-crawler/types";

function renderStatusBadge(status: JobStatusType) {
  switch (status) {
    case "completed":
      return (
        <Badge variant="outline" className="text-emerald-500 border-emerald-500/30 bg-emerald-500/10 gap-1 text-xs">
          <CheckCircle2Icon className="h-3 w-3" />
          Completed
        </Badge>
      );
    case "running":
      return (
        <Badge variant="outline" className="text-blue-500 border-blue-500/30 bg-blue-500/10 gap-1 text-xs">
          <Loader2Icon className="h-3 w-3 animate-spin" />
          Running
        </Badge>
      );
    case "cancelled":
      return (
        <Badge variant="outline" className="text-amber-500 border-amber-500/30 bg-amber-500/10 gap-1 text-xs">
          <StopCircleIcon className="h-3 w-3" />
          {status}
        </Badge>
      );
    case "failed":
    case "interrupted":
      return (
        <Badge variant="outline" className="text-red-500 border-red-500/30 bg-red-500/10 gap-1 text-xs">
          <XCircleIcon className="h-3 w-3" />
          {status}
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="text-muted-foreground gap-1 text-xs">
          <ClockIcon className="h-3 w-3" />
          {status}
        </Badge>
      );
  }
}

function ProjectDetailContent() {
  const params = useParams<{ slug: string }>();
  const searchParams = useSearchParams();
  const slug = params?.slug || "";
  const bucket = searchParams.get("bucket") || "site-crawler";

  const [project, setProject] = React.useState<ProjectDetail | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Raw Page Markdown Sheet State
  const [selectedPage, setSelectedPage] = React.useState<PageResult | null>(null);
  const [pageDetail, setPageDetail] = React.useState<PageDetailResponse | null>(null);
  const [isPageLoading, setIsPageLoading] = React.useState(false);
  const [sheetOpen, setSheetOpen] = React.useState(false);

  const fetchProject = React.useCallback(async () => {
    if (!slug) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/tools/site-crawler/projects/${slug}?bucket=${encodeURIComponent(bucket)}`);
      if (res.ok) {
        const data = await res.json();
        setProject(data);
      } else {
        const err = await res.json().catch(() => ({}));
        setError(err.error?.message || err.detail || `Failed to load project '${slug}'`);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLoading(false);
    }
  }, [slug, bucket]);

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchProject();
  }, [fetchProject]);

  const handleOpenPageDetail = async (page: PageResult) => {
    setSelectedPage(page);
    setSheetOpen(true);
    setIsPageLoading(true);
    setPageDetail(null);
    try {
      const res = await fetch(
        `/api/tools/site-crawler/projects/${slug}/pages/${page.hash}?bucket=${encodeURIComponent(bucket)}`
      );
      if (res.ok) {
        const data = await res.json();
        setPageDetail(data);
      } else {
        const err = await res.json().catch(() => ({}));
        console.error("Failed to load page detail:", err);
      }
    } catch (e) {
      console.error("Error loading page detail:", e);
    } finally {
      setIsPageLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
        <Loader2Icon className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="text-xs text-muted-foreground">Loading project details...</span>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="p-6 max-w-4xl mx-auto space-y-4">
        <Link href="/tools/site-crawler">
          <Button variant="ghost" size="sm" className="gap-1.5 text-xs">
            <ArrowLeftIcon className="h-3.5 w-3.5" />
            Back to Site Crawler
          </Button>
        </Link>
        <Card className="border-destructive/40 bg-destructive/10">
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-destructive">Error Loading Project</CardTitle>
            <CardDescription className="text-xs text-destructive/80">
              {error || "Project not found or failed to load."}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const { manifest, schema, records } = project;
  const counts = manifest.counts || { total: 0, crawled: 0, extracted: 0, failed: 0, records: 0 };

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Navigation & Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link href="/tools/site-crawler">
            <Button variant="outline" size="icon" className="h-8 w-8">
              <ArrowLeftIcon className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-foreground">{manifest.name}</h1>
              {renderStatusBadge(manifest.status)}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono mt-0.5">
              <span>{manifest.slug}</span>
              <span>•</span>
              <span>bucket: {manifest.bucket}</span>
              {manifest.created_at && (
                <>
                  <span>•</span>
                  <span>{new Date(manifest.created_at).toLocaleString()}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchProject}
            disabled={isLoading}
            className="text-xs gap-1.5 h-8"
          >
            <RotateCwIcon className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          {/* Download JSON */}
          <a
            href={`/api/tools/site-crawler/projects/${manifest.slug}/data?bucket=${encodeURIComponent(bucket)}`}
            download
          >
            <Button variant="outline" size="sm" className="text-xs gap-1.5 h-8">
              <FileJsonIcon className="h-3.5 w-3.5 text-blue-500" />
              Download data.json
            </Button>
          </a>

          {/* Download ZIP */}
          <a
            href={`/api/tools/site-crawler/projects/${manifest.slug}/zip?bucket=${encodeURIComponent(bucket)}`}
            download
          >
            <Button size="sm" className="text-xs gap-1.5 h-8">
              <ArchiveIcon className="h-3.5 w-3.5" />
              Export Project (.zip)
            </Button>
          </a>
        </div>
      </div>

      {/* Stats Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="border-border/60 p-4">
          <div className="text-xs text-muted-foreground">Total URLs</div>
          <div className="text-xl font-bold font-mono mt-1">{counts.total}</div>
        </Card>
        <Card className="border-border/60 p-4">
          <div className="text-xs text-muted-foreground">Pages Crawled</div>
          <div className="text-xl font-bold font-mono text-emerald-500 mt-1">{counts.crawled}</div>
        </Card>
        <Card className="border-border/60 p-4">
          <div className="text-xs text-muted-foreground">Extracted Records</div>
          <div className="text-xl font-bold font-mono text-primary mt-1">{counts.records}</div>
        </Card>
        <Card className="border-border/60 p-4">
          <div className="text-xs text-muted-foreground">Failed / Skipped</div>
          <div className="text-xl font-bold font-mono text-amber-500 mt-1">{counts.failed}</div>
        </Card>
      </div>

      {/* Main Tabs: Records, Crawled Pages, Schema */}
      <Tabs defaultValue="records" className="space-y-4">
        <TabsList className="h-9">
          <TabsTrigger value="records" className="text-xs gap-1.5">
            <SparklesIcon className="h-3.5 w-3.5 text-primary" />
            Extracted Records ({records.length})
          </TabsTrigger>
          <TabsTrigger value="pages" className="text-xs gap-1.5">
            <FileTextIcon className="h-3.5 w-3.5" />
            Crawled Pages ({manifest.pages?.length || 0})
          </TabsTrigger>
          <TabsTrigger value="schema" className="text-xs gap-1.5">
            <FileCodeIcon className="h-3.5 w-3.5" />
            Extraction Schema
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Extracted Records */}
        <TabsContent value="records" className="space-y-4">
          {records.length > 0 ? (
            <ResultsTable
              records={records}
              schema={schema || { mode: "single", fields: [], version: 1 }}
            />
          ) : (
            <Card className="border-border/60 p-8 text-center text-muted-foreground text-xs">
              No extracted records available for this project.
            </Card>
          )}
        </TabsContent>

        {/* Tab 2: Crawled Pages Table */}
        <TabsContent value="pages" className="space-y-4">
          <Card className="border-border/60 shadow-sm overflow-hidden">
            <CardHeader className="py-3 px-4 border-b border-border/50">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Crawled Page Manifest
              </CardTitle>
              <CardDescription className="text-xs">
                Inspect raw scraped markdown and per-page extraction results stored in RustFS.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader className="bg-muted/40">
                  <TableRow>
                    <TableHead className="text-xs font-semibold">URL</TableHead>
                    <TableHead className="text-xs font-semibold">Crawl Status</TableHead>
                    <TableHead className="text-xs font-semibold">Extraction</TableHead>
                    <TableHead className="text-xs font-semibold">Records</TableHead>
                    <TableHead className="text-xs font-semibold text-right">Raw Markdown</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {manifest.pages?.map((p) => (
                    <TableRow key={p.hash} className="hover:bg-muted/20">
                      <TableCell className="font-medium text-xs max-w-md truncate" title={p.url}>
                        <div className="truncate text-foreground">{p.url}</div>
                        {p.title && <div className="text-[10px] text-muted-foreground truncate">{p.title}</div>}
                      </TableCell>
                      <TableCell className="text-xs">
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${
                            p.crawl_status === "crawled"
                              ? "text-emerald-500 border-emerald-500/20 bg-emerald-500/5"
                              : p.crawl_status === "crawl_failed"
                              ? "text-red-500 border-red-500/20 bg-red-500/5"
                              : "text-muted-foreground"
                          }`}
                        >
                          {p.crawl_status} {p.http_status ? `(${p.http_status})` : ""}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs">
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${
                            p.extraction_status === "ok"
                              ? "text-primary border-primary/20 bg-primary/5"
                              : p.extraction_status === "empty_content"
                              ? "text-amber-500 border-amber-500/20 bg-amber-500/5"
                              : p.extraction_status === "extraction_failed"
                              ? "text-red-500 border-red-500/20 bg-red-500/5"
                              : "text-muted-foreground"
                          }`}
                        >
                          {p.extraction_status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs font-mono">{p.record_count}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenPageDetail(p)}
                          className="h-7 text-xs gap-1"
                        >
                          <FileTextIcon className="h-3.5 w-3.5 text-muted-foreground" />
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {(!manifest.pages || manifest.pages.length === 0) && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-xs text-muted-foreground">
                        No pages recorded for this project run.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 3: Extraction Schema */}
        <TabsContent value="schema" className="space-y-4">
          <Card className="border-border/60">
            <CardHeader className="py-3 px-4 border-b border-border/50">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Schema Configuration
              </CardTitle>
              <CardDescription className="text-xs">
                Data structure prompt applied to the LLM during markdown extraction.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4">
              <pre className="p-4 rounded-md bg-muted/40 border border-border/50 font-mono text-xs overflow-x-auto text-foreground">
                {JSON.stringify(schema, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Slide-over Sheet for Raw Markdown Inspection */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent
          side="right"
          className="sm:max-w-2xl w-[90vw] p-0 flex flex-col gap-0 border-l border-border/60 bg-background"
        >
          <SheetHeader className="p-4 border-b border-border/60">
            <SheetTitle className="text-sm font-semibold truncate" title={selectedPage?.url}>
              {selectedPage?.title || selectedPage?.url}
            </SheetTitle>
            <SheetDescription className="text-xs font-mono truncate text-muted-foreground">
              {selectedPage?.url}
            </SheetDescription>
          </SheetHeader>

          <div className="flex-1 overflow-y-auto p-4">
            {isPageLoading ? (
              <div className="flex flex-col items-center justify-center h-48 gap-2">
                <Loader2Icon className="h-5 w-5 animate-spin text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Loading raw markdown from RustFS...</span>
              </div>
            ) : pageDetail ? (
              <div className="space-y-4">
                <MarkdownViewer
                  markdown={pageDetail.markdown}
                  title={selectedPage?.title || selectedPage?.url}
                  url={selectedPage?.url}
                />
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-muted-foreground">
                No raw markdown available for this page.
              </div>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default function ProjectDetailPage() {
  return (
    <React.Suspense
      fallback={
        <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
          <Loader2Icon className="h-6 w-6 animate-spin text-muted-foreground" />
          <span className="text-xs text-muted-foreground">Loading project...</span>
        </div>
      }
    >
      <ProjectDetailContent />
    </React.Suspense>
  );
}
