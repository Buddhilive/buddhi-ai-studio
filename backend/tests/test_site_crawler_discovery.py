import gzip
import pytest
import httpx

from app.services.site_crawler.discovery import (
    apply_glob_filters,
    fetch_and_parse_sitemap,
    fetch_robots_txt,
    normalize_url,
)


def test_normalize_url():
    url = "https://Example.COM/products/shoes/?utm_source=google&color=red#overview"
    norm = normalize_url(url)
    assert norm == "https://example.com/products/shoes?color=red"


def test_apply_glob_filters():
    assert apply_glob_filters("https://example.com/blog/post-1", ["/blog/*"], []) is True
    assert apply_glob_filters("https://example.com/admin/settings", [], ["/admin/*"]) is False
    assert apply_glob_filters("https://example.com/products/p1", ["/blog/*"], []) is False


@pytest.mark.asyncio
async def test_fetch_robots_txt():
    robots_content = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Sitemap: https://example.com/custom-sitemap.xml\n"
    )

    async def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=robots_content)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        rp, sitemaps = await fetch_robots_txt(client, "https://example.com")
        assert len(sitemaps) == 1
        assert sitemaps[0] == "https://example.com/custom-sitemap.xml"
        assert rp.can_fetch("Buddhi-AI-Studio", "https://example.com/public") is True
        assert rp.can_fetch("Buddhi-AI-Studio", "https://example.com/admin/dash") is False


@pytest.mark.asyncio
async def test_fetch_and_parse_sitemap_regular():
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>https://example.com/page-1</loc></url>\n'
        '  <url><loc>https://example.com/page-2</loc></url>\n'
        '  <url><loc>https://other.com/page-3</loc></url>\n'
        '</urlset>'
    )

    async def mock_handler(request: httpx.Request):
        return httpx.Response(200, content=xml.encode("utf-8"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        urls = await fetch_and_parse_sitemap(client, "https://example.com/sitemap.xml", "example.com")
        assert len(urls) == 2
        assert "https://example.com/page-1" in urls
        assert "https://example.com/page-2" in urls


@pytest.mark.asyncio
async def test_fetch_and_parse_sitemap_gzip():
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>https://example.com/gzipped-page</loc></url>\n'
        '</urlset>'
    )
    compressed = gzip.compress(xml.encode("utf-8"))

    async def mock_handler(request: httpx.Request):
        return httpx.Response(200, content=compressed, headers={"content-type": "application/x-gzip"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        urls = await fetch_and_parse_sitemap(client, "https://example.com/sitemap.xml.gz", "example.com")
        assert len(urls) == 1
        assert urls[0] == "https://example.com/gzipped-page"
