export type FieldType = "string" | "number" | "boolean" | "string_list" | "object";

export interface FieldDefinition {
  name: string;
  type: FieldType;
  description: string;
  required: boolean;
  fields?: FieldDefinition[];
}

export type ExtractionMode = "single" | "many";

export interface ExtractionSchema {
  mode: ExtractionMode;
  fields: FieldDefinition[];
  version: number;
}

export interface DiscoveredUrl {
  url: string;
  root: string;
  source: "sitemap" | "links" | "manual";
  allowed: boolean;
  selected: boolean;
}

export interface DiscoverRootSummary {
  root: string;
  source: string;
  count: number;
  truncated: boolean;
  error?: string;
}

export interface DiscoverResponse {
  urls: DiscoveredUrl[];
  per_root: DiscoverRootSummary[];
}

export interface CrawlOptions {
  only_main_content: boolean;
  timeout_s: number;
  bypass_cache: boolean;
}

export interface CreateJobRequest {
  project_name: string;
  bucket: string;
  urls: string[];
  schema: ExtractionSchema;
  include_patterns?: string[];
  exclude_patterns?: string[];
  max_pages?: number;
  ignore_robots?: boolean;
  model_id?: string;
  crawl_options?: Partial<CrawlOptions>;
}

export type JobStatusType =
  | "queued"
  | "discovering"
  | "running"
  | "completed"
  | "cancelled"
  | "failed"
  | "interrupted";

export interface JobCounts {
  total: number;
  crawled: number;
  extracted: number;
  failed: number;
  records: number;
}

export interface RecentError {
  url: string;
  error: string;
}

export interface JobStatus {
  job_id: string;
  bucket: string;
  slug: string;
  status: JobStatusType;
  counts: JobCounts;
  current_url?: string;
  started_at?: string;
  elapsed_s?: number;
  cap_applied?: boolean;
  recent_errors: RecentError[];
}

export interface PageResult {
  url: string;
  hash: string;
  crawl_status: "pending" | "crawling" | "crawled" | "crawl_failed" | "skipped";
  extraction_status:
    | "pending"
    | "extracting"
    | "ok"
    | "empty_content"
    | "extraction_failed"
    | "skipped";
  http_status?: number;
  title?: string;
  record_count: number;
  error?: string;
  crawl_ms?: number;
  extract_ms?: number;
  attempts: number;
}

export interface ProjectManifest {
  name: string;
  slug: string;
  bucket: string;
  job_id: string;
  created_at: string;
  updated_at: string;
  started_at?: string;
  finished_at?: string;
  status: JobStatusType;
  settings: Record<string, unknown>;
  counts: JobCounts;
  current_url?: string;
  pages: PageResult[];
  model_id?: string;
  error?: string;
}

export interface ProjectSummary {
  name: string;
  slug: string;
  bucket: string;
  created_at: string;
  status: JobStatusType;
  counts: JobCounts;
}

export interface SiteCrawlerHealth {
  crawl4ai: boolean;
  storage: boolean;
  model: {
    available: boolean;
    model_id?: string;
    error?: string;
  };
  ready: boolean;
}

export interface BucketInfo {
  name: string;
  created_at?: string;
}

export interface ProjectDetail {
  manifest: ProjectManifest;
  schema?: ExtractionSchema;
  records: Record<string, unknown>[];
}

export interface PageDetailResponse {
  markdown: string;
  meta: Record<string, unknown>;
  records: Record<string, unknown>[];
}
