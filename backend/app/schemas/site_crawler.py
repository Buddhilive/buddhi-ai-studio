import re
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


FieldType = Literal["string", "number", "boolean", "string_list", "object"]


class FieldDefinition(BaseModel):
    name: str = Field(..., description="Field identifier")
    type: FieldType = Field(..., description="Data type of the field")
    description: str = Field("", max_length=500, description="Guidance for LLM extraction")
    required: bool = Field(False, description="Whether the field is required")
    fields: list["FieldDefinition"] | None = Field(
        None, description="Sub-fields if type is object (1 level of nesting allowed)"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        name = v.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$", name):
            raise ValueError(
                f"Field name '{name}' is invalid. Must be 1-64 characters starting with a letter or underscore."
            )
        return name


class ExtractionSchema(BaseModel):
    mode: Literal["single", "many"] = Field(
        "single", description="single record per page or array of records per page"
    )
    fields: list[FieldDefinition] = Field(..., min_length=1, max_length=50)
    version: int = Field(1, description="Schema version number")


class DiscoveredUrl(BaseModel):
    url: str
    root: str
    source: Literal["sitemap", "links", "manual"] = "sitemap"
    allowed: bool = True
    selected: bool = True


class DiscoverRootSummary(BaseModel):
    root: str
    source: str
    count: int
    truncated: bool = False
    error: str | None = None


class DiscoverRequest(BaseModel):
    roots: list[str] = Field(..., min_length=1, max_length=10)
    ignore_robots: bool = False


class DiscoverResponse(BaseModel):
    urls: list[DiscoveredUrl]
    per_root: list[DiscoverRootSummary]


class CrawlOptions(BaseModel):
    only_main_content: bool = True
    timeout_s: float = 60.0
    bypass_cache: bool = False


class CreateJobRequest(BaseModel):
    model_config = {"populate_by_name": True}

    project_name: str = Field(..., min_length=1, max_length=100)
    bucket: str = Field(...)
    urls: list[str] = Field(..., min_length=1, max_length=1000)
    extraction_schema: ExtractionSchema = Field(..., alias="schema")
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    max_pages: int = Field(100, ge=1, le=1000)
    ignore_robots: bool = False
    model_id: str | None = None
    crawl_options: CrawlOptions = Field(default_factory=CrawlOptions)


JobStatusType = Literal[
    "queued",
    "discovering",
    "running",
    "completed",
    "cancelled",
    "failed",
    "interrupted",
]


class JobCounts(BaseModel):
    total: int = 0
    crawled: int = 0
    extracted: int = 0
    failed: int = 0
    records: int = 0


class RecentError(BaseModel):
    url: str
    error: str


class JobStatus(BaseModel):
    job_id: str
    bucket: str
    slug: str
    status: JobStatusType
    counts: JobCounts
    current_url: str | None = None
    started_at: str | None = None
    elapsed_s: float = 0.0
    cap_applied: bool = False
    recent_errors: list[RecentError] = Field(default_factory=list)


class PageResult(BaseModel):
    url: str
    hash: str
    crawl_status: Literal["pending", "crawling", "crawled", "crawl_failed", "skipped"] = "pending"
    extraction_status: Literal[
        "pending",
        "extracting",
        "ok",
        "empty_content",
        "extraction_failed",
        "skipped",
    ] = "pending"
    http_status: int | None = None
    title: str | None = None
    record_count: int = 0
    error: str | None = None
    crawl_ms: float = 0.0
    extract_ms: float = 0.0
    attempts: int = 0


class ProjectManifest(BaseModel):
    name: str
    slug: str
    bucket: str
    job_id: str
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    status: JobStatusType = "queued"
    settings: dict[str, Any] = Field(default_factory=dict)
    counts: JobCounts = Field(default_factory=JobCounts)
    current_url: str | None = None
    pages: list[PageResult] = Field(default_factory=list)
    model_id: str | None = None
    error: str | None = None


class ProjectSummary(BaseModel):
    name: str
    slug: str
    bucket: str
    created_at: str
    status: JobStatusType
    counts: JobCounts


class SiteCrawlerHealth(BaseModel):
    crawl4ai: bool
    storage: bool
    model: dict[str, Any]
    ready: bool


class DataFile(BaseModel):
    model_config = {"populate_by_name": True}

    project: dict[str, Any]
    extraction_schema: ExtractionSchema = Field(..., alias="schema")
    records: list[dict[str, Any]]
