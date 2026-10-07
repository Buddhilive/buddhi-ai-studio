import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.crawl import CrawlBatchRequest, CrawlResult
from app.services.crawl_service import CrawlService


@pytest.mark.asyncio
async def test_crawl_service_job_lifecycle():
    service = CrawlService(base_url="http://mock-crawl4ai:11235")

    mock_res = CrawlResult(
        url="https://example.com/1",
        status="completed",
        title="Title 1",
        markdown="Content 1",
        status_code=200,
        links_count=0,
        media_count=0,
        execution_duration_ms=45.0,
    )

    with patch.object(service, "crawl", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.return_value = mock_res
        req = CrawlBatchRequest(urls=["https://example.com/1"])
        job = await service.create_job(req)

        assert job.job_id is not None
        assert job.status in ("pending", "processing", "completed")
        assert job.total_urls == 1

        # Wait briefly for background asyncio task to complete
        await asyncio.sleep(0.1)

        completed_job = await service.get_job(job.job_id)
        assert completed_job is not None
        assert completed_job.status == "completed"
        assert len(completed_job.results) == 1
        assert completed_job.results[0].title == "Title 1"


def test_crawl_job_router_endpoints():
    client = TestClient(app)

    # 1. Post job
    with patch("app.routers.crawl.crawl_service.create_job", new_callable=AsyncMock) as mock_create:
        from app.schemas.crawl import CrawlJobResponse
        from datetime import datetime, timezone
        mock_job = CrawlJobResponse(
            job_id="test-job-uuid-1234",
            status="pending",
            created_at=datetime.now(timezone.utc),
            total_urls=1,
            completed_urls=0,
            results=[],
        )
        mock_create.return_value = mock_job

        res = client.post("/v1/crawl/jobs", json={"urls": ["https://example.com/item"]})
        assert res.status_code == 202
        data = res.json()
        assert data["job_id"] == "test-job-uuid-1234"
        assert data["status"] == "pending"

    # 2. Get existing job
    with patch("app.routers.crawl.crawl_service.get_job", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_job
        res = client.get("/v1/crawl/jobs/test-job-uuid-1234")
        assert res.status_code == 200
        assert res.json()["job_id"] == "test-job-uuid-1234"

    # 3. Get non-existent job
    with patch("app.routers.crawl.crawl_service.get_job", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        res = client.get("/v1/crawl/jobs/non-existent-uuid")
        assert res.status_code == 404
