from datetime import datetime
import ipaddress
import socket
from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator


def validate_crawl_url(url: str, allow_private: bool = False) -> str:
    """
    Validate that the URL has an HTTP/HTTPS scheme and does not target
    private, loopback, or cloud-metadata IP addresses (SSRF prevention).
    """
    cleaned = url.strip()
    if not cleaned:
        raise ValueError("URL cannot be empty.")

    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{parsed.scheme}'. Only http and https are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must include a valid hostname.")

    if not allow_private:
        # Check direct localhost string
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            raise ValueError(f"Requests to local address '{hostname}' are blocked for security.")

        # Check if hostname is an IP address
        try:
            ip = ipaddress.ip_address(hostname)
            is_ip = True
        except ValueError:
            is_ip = False

        if is_ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved):
            raise ValueError(f"Requests to private/internal IP '{hostname}' are blocked for security.")


    return cleaned


class CrawlRequest(BaseModel):
    url: str = Field(..., description="Target webpage URL to crawl")
    css_selector: str | None = Field(None, description="CSS selector to isolate specific elements")
    only_main_content: bool = Field(True, description="Filter out headers, navbars, and footers for clean markdown")
    wait_for: float | str | None = Field(None, description="Wait duration in seconds or CSS selector before extraction")
    js_code: str | None = Field(None, description="JavaScript snippet to execute on page prior to crawl")
    bypass_cache: bool = Field(False, description="Bypass server-side crawler cache")
    timeout_s: int = Field(60, ge=5, le=300, description="Crawl timeout in seconds")

    @field_validator("url")
    @classmethod
    def check_url(cls, v: str) -> str:
        return validate_crawl_url(v)


class CrawlResult(BaseModel):
    url: str = Field(..., description="Target URL that was crawled")
    status: Literal["completed", "failed", "timeout"] = Field(..., description="Outcome of the crawl operation")
    title: str = Field("", description="Extracted HTML page title")
    markdown: str = Field("", description="Clean, LLM-optimized markdown content")
    html: str | None = Field(None, description="Raw or pruned HTML content (optional)")
    status_code: int = Field(200, description="HTTP response code of the fetched webpage")
    links_count: int = Field(0, description="Number of discovered hyperlinks on the page")
    media_count: int = Field(0, description="Number of discovered images or media elements")
    execution_duration_ms: float = Field(..., description="Total wall-clock duration in milliseconds")
    error: str | None = Field(None, description="Error message if the crawl failed")


class CrawlBatchRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, max_length=50, description="List of URLs to crawl in batch")
    css_selector: str | None = Field(None, description="Global CSS selector applied to all URLs")
    only_main_content: bool = Field(True, description="Filter out headers/footers for clean markdown")
    wait_for: float | str | None = Field(None, description="Wait duration or selector")
    bypass_cache: bool = Field(False, description="Bypass crawler cache")
    timeout_s: int = Field(120, ge=10, le=600, description="Per-job timeout in seconds")

    @field_validator("urls")
    @classmethod
    def check_urls(cls, v: list[str]) -> list[str]:
        return [validate_crawl_url(u) for u in v]


class CrawlJobResponse(BaseModel):
    job_id: str = Field(..., description="Unique UUID identifying the async crawl job")
    status: Literal["pending", "processing", "completed", "failed"] = Field(..., description="Job lifecycle status")
    created_at: datetime = Field(..., description="Timestamp when job was queued")
    completed_at: datetime | None = Field(None, description="Timestamp when job finished")
    total_urls: int = Field(1, description="Total number of URLs in this batch job")
    completed_urls: int = Field(0, description="Number of URLs processed so far")
    results: list[CrawlResult] = Field(default_factory=list, description="Array of results for completed URLs")
    error: str | None = Field(None, description="Failure reason if the entire job failed")


class CrawlHealthStatus(BaseModel):
    status: Literal["healthy", "unhealthy"] = Field(..., description="Health status of Crawl4AI service")
    service_url: str = Field(..., description="Configured Crawl4AI upstream server URL")
    version: str | None = Field(None, description="Upstream Crawl4AI engine version if available")
    latency_ms: float = Field(0.0, description="Health probe round-trip latency in milliseconds")
    error: str | None = Field(None, description="Connection error details if unhealthy")
