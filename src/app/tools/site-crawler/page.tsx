"use client";

import * as React from "react";
import {
  GlobeIcon,
  PlayIcon,
  RotateCwIcon,
  SparklesIcon,
  LayersIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ServiceStatusBanner } from "@/components/site-crawler/service-status-banner";
import { ProjectSetupCard } from "@/components/site-crawler/project-setup-card";
import { UrlInputCard } from "@/components/site-crawler/url-input";
import { DiscoveryTable } from "@/components/site-crawler/discovery-table";
import { SchemaBuilder } from "@/components/site-crawler/schema-builder";
import { ResultsTable } from "@/components/site-crawler/results-table";
import { JobProgressCard } from "@/components/site-crawler/job-progress";
import { ProjectsList } from "@/components/site-crawler/projects-list";
import {
  BucketInfo,
  CreateJobRequest,
  DiscoveredUrl,
  ExtractionSchema,
  JobStatus,
  SiteCrawlerHealth,
} from "@/lib/site-crawler/types";

const DEFAULT_SCHEMA: ExtractionSchema = {
  mode: "single",
  fields: [
    { name: "title", type: "string", description: "Main heading or product title", required: true },
    { name: "description", type: "string", description: "Summary or description paragraph", required: false },
    { name: "price", type: "number", description: "Numeric cost or price if present", required: false },
  ],
  version: 1,
};

export default function SiteCrawlerPage() {
  const [activeTab, setActiveTab] = React.useState<string>("new");

  // Health
  const [health, setHealth] = React.useState<SiteCrawlerHealth | null>(null);
  const [isHealthLoading, setIsHealthLoading] = React.useState(false);

  // Storage Buckets
  const [buckets, setBuckets] = React.useState<BucketInfo[]>([]);
  const [selectedBucket, setSelectedBucket] = React.useState<string>("site-crawler");

  // Form State
  const [projectName, setProjectName] = React.useState<string>("");
  const [rawUrls, setRawUrls] = React.useState<string>("");
  const [enableDiscovery, setEnableDiscovery] = React.useState<boolean>(false);
  const [isDiscovering, setIsDiscovering] = React.useState<boolean>(false);
  const [discoveredUrls, setDiscoveredUrls] = React.useState<DiscoveredUrl[]>([]);
  const [selectedUrls, setSelectedUrls] = React.useState<Set<string>>(new Set());
  const [maxPages, setMaxPages] = React.useState<number>(100);
  const [ignoreRobots, setIgnoreRobots] = React.useState<boolean>(false);
  const [schema, setSchema] = React.useState<ExtractionSchema>(DEFAULT_SCHEMA);

  // Execution State
  const [isSubmitting, setIsSubmitting] = React.useState<boolean>(false);
  const [isCancelling, setIsCancelling] = React.useState<boolean>(false);
  const [jobStatus, setJobStatus] = React.useState<JobStatus | null>(null);
  const [extractedRecords, setExtractedRecords] = React.useState<Record<string, unknown>[]>([]);
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  // Fetch Health & Buckets
  const fetchHealth = React.useCallback(async () => {
    setIsHealthLoading(true);
    try {
      const res = await fetch("/api/tools/site-crawler/health");
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch {
      // Ignored
    } finally {
      setIsHealthLoading(false);
    }
  }, []);

  const fetchBuckets = React.useCallback(async () => {
    try {
      const res = await fetch("/api/storage/buckets");
      if (res.ok) {
        const data = await res.json();
        setBuckets(data.buckets || []);
        if (data.default_bucket) {
          setSelectedBucket((curr) => curr || data.default_bucket);
        }
      }
    } catch {
      // Ignored
    }
  }, []);

  React.useEffect(() => {
    fetchHealth();
    fetchBuckets();

    // Check for reattachment from localStorage
    try {
      const saved = localStorage.getItem("site_crawler_last_job");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.job_id && parsed.bucket) {
          setJobStatus({
            job_id: parsed.job_id,
            bucket: parsed.bucket,
            slug: parsed.slug || "",
            status: "running",
            counts: { total: 0, crawled: 0, extracted: 0, failed: 0, records: 0 },
            recent_errors: [],
          });
        }
      }
    } catch {
      // Ignored
    }
  }, [fetchHealth, fetchBuckets]);

  // Polling Job Status
  React.useEffect(() => {
    if (!jobStatus?.job_id) return;
    const isTerminal = ["completed", "cancelled", "failed", "interrupted"].includes(jobStatus.status);
    if (isTerminal) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(
          `/api/tools/site-crawler/jobs/${jobStatus.job_id}?bucket=${encodeURIComponent(jobStatus.bucket)}`
        );
        if (res.ok) {
          const updated: JobStatus = await res.json();
          setJobStatus(updated);

          // If job finished, fetch records from project detail
          if (["completed", "cancelled"].includes(updated.status)) {
            const pRes = await fetch(
              `/api/tools/site-crawler/projects/${updated.slug}?bucket=${encodeURIComponent(updated.bucket)}`
            );
            if (pRes.ok) {
              const pData = await pRes.json();
              setExtractedRecords(pData.records || []);
            }
          }
        }
      } catch {
        // Polling error ignored
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [jobStatus?.job_id, jobStatus?.status, jobStatus?.bucket, jobStatus?.slug]);

  const handleCancelJob = async () => {
    if (!jobStatus?.job_id) return;
    setIsCancelling(true);
    try {
      const res = await fetch(`/api/tools/site-crawler/jobs/${jobStatus.job_id}/cancel`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setJobStatus(data);
      }
    } catch {
      // Ignored
    } finally {
      setIsCancelling(false);
    }
  };

  const handleDiscover = async () => {
    const roots = rawUrls
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);

    if (roots.length === 0) {
      setSubmitError("Please enter at least one root URL to scan.");
      return;
    }

    setIsDiscovering(true);
    setSubmitError(null);

    try {
      const res = await fetch("/api/tools/site-crawler/discover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ roots, ignore_robots: ignoreRobots }),
      });

      const data = await res.json();
      if (!res.ok) {
        setSubmitError(data.error?.message || data.detail || "URL discovery failed");
      } else {
        const urls: DiscoveredUrl[] = data.urls || [];
        setDiscoveredUrls(urls);
        const autoSelected = new Set(urls.filter((u) => u.selected).map((u) => u.url));
        setSelectedUrls(autoSelected);
      }
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsDiscovering(false);
    }
  };

  const handleStartRun = async () => {
    setSubmitError(null);

    let urls: string[] = [];
    if (enableDiscovery && discoveredUrls.length > 0) {
      urls = Array.from(selectedUrls);
    } else {
      urls = rawUrls
        .split("\n")
        .map((u) => u.trim())
        .filter(Boolean);
    }

    if (!projectName.trim()) {
      setSubmitError("Please provide a project name.");
      return;
    }
    if (!selectedBucket.trim()) {
      setSubmitError("Please select a storage bucket.");
      return;
    }
    if (urls.length === 0) {
      setSubmitError(
        enableDiscovery && discoveredUrls.length > 0
          ? "Please select at least one discovered URL to crawl."
          : "Please provide at least one target URL."
      );
      return;
    }
    if (schema.fields.length === 0) {
      setSubmitError("Please define at least one schema field to extract.");
      return;
    }

    setIsSubmitting(true);
    setExtractedRecords([]);

    try {
      const payload: CreateJobRequest = {
        project_name: projectName.trim(),
        bucket: selectedBucket,
        urls,
        schema,
        max_pages: maxPages,
        ignore_robots: ignoreRobots,
      };

      const res = await fetch("/api/tools/site-crawler/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        setSubmitError(data.error?.message || data.detail || "Failed to start extraction job");
      } else {
        setJobStatus(data);
        try {
          localStorage.setItem(
            "site_crawler_last_job",
            JSON.stringify({ job_id: data.job_id, bucket: data.bucket, slug: data.slug })
          );
        } catch {
          // Ignored
        }
      }
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const isFormValid =
    projectName.trim().length > 0 &&
    selectedBucket.trim().length > 0 &&
    (enableDiscovery ? (discoveredUrls.length === 0 || selectedUrls.size > 0) : rawUrls.trim().length > 0) &&
    schema.fields.length > 0;

  const isJobRunning = jobStatus && ["queued", "running", "discovering"].includes(jobStatus.status);

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 sm:p-6 max-w-7xl mx-auto w-full">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/40 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <GlobeIcon className="h-5 w-5" />
            </div>
            <h1 className="text-xl font-bold tracking-tight">Site Crawler & Extractor</h1>
            <Badge variant="outline" className="text-xs font-mono gap-1 ml-1 border-primary/30 text-primary">
              <SparklesIcon className="h-3 w-3" />
              Local LLM
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Crawl websites via Crawl4AI, discover sitemaps, and extract structured datasets directly to RustFS using local LLM inferencing.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 text-xs self-start sm:self-auto"
          onClick={() => {
            fetchHealth();
            fetchBuckets();
          }}
          disabled={isHealthLoading}
        >
          <RotateCwIcon className={`h-3.5 w-3.5 ${isHealthLoading ? "animate-spin" : ""}`} />
          Refresh Status
        </Button>
      </div>

      {/* Service Health Banner */}
      <ServiceStatusBanner health={health} />

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="new" className="text-xs gap-1.5">
            <PlayIcon className="h-3.5 w-3.5" />
            New Extraction Project
          </TabsTrigger>
          <TabsTrigger value="projects" className="text-xs gap-1.5">
            <LayersIcon className="h-3.5 w-3.5" />
            Saved Projects
          </TabsTrigger>
        </TabsList>

        <TabsContent value="new" className="space-y-6">
          {/* Step 1: Project & Bucket */}
          <ProjectSetupCard
            projectName={projectName}
            onProjectNameChange={setProjectName}
            bucket={selectedBucket}
            onBucketChange={setSelectedBucket}
            buckets={buckets}
            onBucketCreated={(b) => setBuckets((curr) => [...curr, { name: b }])}
            disabled={Boolean(isJobRunning)}
          />

          {/* Step 2: Target URLs */}
          <UrlInputCard
            rawUrls={rawUrls}
            onRawUrlsChange={setRawUrls}
            enableDiscovery={enableDiscovery}
            onEnableDiscoveryChange={setEnableDiscovery}
            onDiscover={handleDiscover}
            isDiscovering={isDiscovering}
            maxPages={maxPages}
            onMaxPagesChange={setMaxPages}
            ignoreRobots={ignoreRobots}
            onIgnoreRobotsChange={setIgnoreRobots}
            disabled={Boolean(isJobRunning)}
          />

          {/* Discovery Table (if discovery returned URLs) */}
          {enableDiscovery && discoveredUrls.length > 0 && (
            <DiscoveryTable
              discoveredUrls={discoveredUrls}
              selectedUrls={selectedUrls}
              onSelectionChange={setSelectedUrls}
              maxPages={maxPages}
            />
          )}

          {/* Step 3: Schema Definition */}
          <SchemaBuilder
            schema={schema}
            onChange={setSchema}
            disabled={Boolean(isJobRunning)}
          />

          {/* Error Message */}
          {submitError && (
            <div className="p-3.5 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs">
              {submitError}
            </div>
          )}

          {/* Run Action */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <Button
              size="default"
              className="px-6 gap-2"
              onClick={handleStartRun}
              disabled={Boolean(!isFormValid || isSubmitting || isJobRunning || (health && !health.ready))}
            >
              <PlayIcon className="h-4 w-4" />
              {isSubmitting ? "Starting..." : isJobRunning ? "Job In Progress..." : "Start Extraction Run"}
            </Button>
          </div>

          {/* Live Progress Card (if job triggered) */}
          {jobStatus && (
            <JobProgressCard
              jobStatus={jobStatus}
              onCancel={handleCancelJob}
              isCancelling={isCancelling}
            />
          )}

          {/* Extracted Records Table */}
          {extractedRecords.length > 0 && (
            <ResultsTable records={extractedRecords} schema={schema} />
          )}
        </TabsContent>

        <TabsContent value="projects">
          <ProjectsList bucket={selectedBucket} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
