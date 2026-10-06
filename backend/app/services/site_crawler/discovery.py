import asyncio
import fnmatch
import gzip
import logging
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
import defusedxml.ElementTree as ET
import httpx

from app.core.config import settings
from app.schemas.crawl import CrawlRequest
from app.schemas.site_crawler import (
    DiscoveredUrl,
    DiscoverResponse,
    DiscoverRootSummary,
)
from app.services.crawl_service import crawl_service

logger = logging.getLogger(__name__)

TRACKING_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
}


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Drop tracking query params
    filtered_qs = []
    if parsed.query:
        for k, v in parse_qsl(parsed.query, keep_blank_values=True):
            if k.lower() not in TRACKING_QUERY_PARAMS:
                filtered_qs.append((k, v))
    new_query = urlencode(filtered_qs)

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    return urlunparse((scheme, netloc, path, "", new_query, ""))


def apply_glob_filters(
    url: str, include_patterns: list[str], exclude_patterns: list[str]
) -> bool:
    parsed = urlparse(url)
    path = parsed.path

    if exclude_patterns:
        for pat in exclude_patterns:
            if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(url, pat):
                return False

    if include_patterns:
        matched = False
        for pat in include_patterns:
            if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(url, pat):
                matched = True
                break
        return matched

    return True


async def fetch_robots_txt(
    client: httpx.AsyncClient, root_url: str
) -> tuple[RobotFileParser, list[str]]:
    parsed = urlparse(root_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = RobotFileParser()
    sitemaps: list[str] = []

    try:
        res = await client.get(robots_url, timeout=10.0)
        if res.is_success and res.text:
            lines = res.text.splitlines()
            rp.parse(lines)
            for line in lines:
                if line.lower().startswith("sitemap:"):
                    parts = line.split(":", 1)
                    if len(parts) == 2 and parts[1].strip():
                        sitemaps.append(parts[1].strip())
    except Exception as exc:
        logger.info("Could not fetch robots.txt for %s: %s", root_url, exc)

    return rp, sitemaps


async def fetch_and_parse_sitemap(
    client: httpx.AsyncClient,
    sitemap_url: str,
    target_host: str,
    depth: int = 1,
    max_depth: int = 3,
) -> list[str]:
    if depth > max_depth:
        return []

    try:
        res = await client.get(sitemap_url, timeout=15.0)
        if not res.is_success or not res.content:
            return []

        content_bytes = res.content
        if sitemap_url.endswith(".gz") or res.headers.get("content-type") == "application/x-gzip":
            try:
                content_bytes = gzip.decompress(content_bytes)
            except Exception as gz_err:
                logger.warning("Gzip decompress failed on %s: %s", sitemap_url, gz_err)
                return []

        # Cap XML size
        if len(content_bytes) > 50 * 1024 * 1024:
            logger.warning("Sitemap XML exceeds 50MB cap on %s", sitemap_url)
            return []

        root = ET.fromstring(content_bytes)
        urls: list[str] = []

        # Check if sitemap index
        # Strip XML namespaces
        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        if tag == "sitemapindex":
            child_sitemaps = []
            for sm in root:
                for elem in sm:
                    elem_tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if elem_tag == "loc" and elem.text:
                        child_sitemaps.append(elem.text.strip())

            for child in child_sitemaps:
                child_urls = await fetch_and_parse_sitemap(
                    client, child, target_host, depth=depth + 1, max_depth=max_depth
                )
                urls.extend(child_urls)
        else:
            # Regular urlset
            for url_elem in root:
                for elem in url_elem:
                    elem_tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if elem_tag == "loc" and elem.text:
                        loc = elem.text.strip()
                        p = urlparse(loc)
                        if p.netloc.lower() == target_host:
                            urls.append(normalize_url(loc))

        return urls

    except Exception as exc:
        logger.warning("Failed to parse sitemap %s: %s", sitemap_url, exc)
        return []


async def discover_via_crawl_fallback(
    root_url: str, target_host: str, max_depth: int = 2
) -> list[str]:
    discovered: set[str] = {normalize_url(root_url)}
    queue: list[tuple[str, int]] = [(normalize_url(root_url), 1)]

    while queue:
        curr_url, curr_depth = queue.pop(0)
        if curr_depth > max_depth:
            continue

        try:
            req = CrawlRequest(url=curr_url, timeout_s=35.0, bypass_cache=True)
            res = await crawl_service.crawl(req)
            for link in res.internal_links:
                full_url = urljoin(curr_url, link)
                p = urlparse(full_url)
                if p.scheme in ("http", "https") and p.netloc.lower() == target_host:
                    norm = normalize_url(full_url)
                    if norm not in discovered:
                        discovered.add(norm)
                        if curr_depth + 1 <= max_depth:
                            queue.append((norm, curr_depth + 1))
        except Exception as exc:
            logger.info("Crawl fallback failed on %s: %s", curr_url, exc)

    return list(discovered)


async def discover_urls_for_root(
    client: httpx.AsyncClient,
    root_url: str,
    ignore_robots: bool = False,
) -> tuple[list[DiscoveredUrl], DiscoverRootSummary]:
    parsed_root = urlparse(root_url)
    target_host = parsed_root.netloc.lower()
    scheme = parsed_root.scheme.lower() or "https"

    rp, sitemap_candidates = await fetch_robots_txt(client, root_url)

    if not sitemap_candidates:
        sitemap_candidates = [
            f"{scheme}://{target_host}/sitemap.xml",
            f"{scheme}://{target_host}/sitemap_index.xml",
        ]

    discovered_raw_urls: set[str] = set()
    source_used = "sitemap"

    for sm_url in sitemap_candidates:
        urls = await fetch_and_parse_sitemap(client, sm_url, target_host)
        for u in urls:
            discovered_raw_urls.add(u)

    # Fallback to Crawl4AI link-following if sitemaps empty
    if not discovered_raw_urls:
        source_used = "links"
        fallback_urls = await discover_via_crawl_fallback(root_url, target_host, max_depth=2)
        for u in fallback_urls:
            discovered_raw_urls.add(u)

    if not discovered_raw_urls:
        # Default fallback to just the root URL
        discovered_raw_urls.add(normalize_url(root_url))
        source_used = "manual"

    # Evaluate robots.txt and package into DiscoveredUrl
    results: list[DiscoveredUrl] = []
    user_agent = "Buddhi-AI-Studio"

    for u in sorted(discovered_raw_urls):
        allowed = True
        if not ignore_robots:
            try:
                allowed = rp.can_fetch(user_agent, u)
            except Exception:
                allowed = True

        results.append(
            DiscoveredUrl(
                url=u,
                root=root_url,
                source=source_used,
                allowed=allowed,
                selected=allowed,
            )
        )

    summary = DiscoverRootSummary(
        root=root_url,
        source=source_used,
        count=len(results),
        truncated=False,
    )
    return results, summary


async def discover_all(
    roots: list[str], ignore_robots: bool = False
) -> DiscoverResponse:
    all_urls: list[DiscoveredUrl] = []
    summaries: list[DiscoverRootSummary] = []

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        follow_redirects=True,
    ) as client:
        for r in roots:
            try:
                urls, summary = await discover_urls_for_root(
                    client, r.strip(), ignore_robots=ignore_robots
                )
                all_urls.extend(urls)
                summaries.append(summary)
            except Exception as exc:
                logger.error("Discovery error on root %s: %s", r, exc)
                summaries.append(
                    DiscoverRootSummary(
                        root=r,
                        source="failed",
                        count=0,
                        truncated=False,
                        error=str(exc),
                    )
                )

    return DiscoverResponse(urls=all_urls, per_root=summaries)
