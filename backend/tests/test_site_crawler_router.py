from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.site_crawler import (
    DataFile,
    ExtractionSchema,
    FieldDefinition,
    JobCounts,
    JobStatus,
    PageResult,
    ProjectManifest,
    ProjectSummary,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_site_crawler_health(client):
    with patch("app.routers.site_crawler.crawl_service.check_health", new_callable=AsyncMock) as mock_crawl, \
         patch("app.routers.site_crawler.storage_service.check_health", new_callable=AsyncMock) as mock_storage, \
         patch("app.routers.site_crawler.model_download_manager.check_availability") as mock_avail:
        
        mock_crawl.return_value = MagicMock(status="healthy")
        mock_storage.return_value = MagicMock(status="healthy")
        mock_avail.return_value = MagicMock(available=True, path="/models/test-qwen")

        resp = client.get("/v1/tools/site-crawler/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["crawl4ai"] is True
        assert data["storage"] is True
        assert data["model"]["available"] is True
        assert data["ready"] is True


def test_create_and_get_job(client):
    req_body = {
        "project_name": "Docs Run",
        "bucket": "test-bucket",
        "urls": ["https://example.com/docs"],
        "schema": {
            "mode": "single",
            "fields": [
                {"name": "title", "type": "string", "description": "Doc title", "required": True}
            ],
            "version": 1,
        },
    }

    mock_status_obj = JobStatus(
        job_id="job-12345678",
        bucket="test-bucket",
        slug="docs-run",
        status="running",
        counts=JobCounts(total=1, crawled=0, extracted=0, failed=0, records=0),
        recent_errors=[],
    )

    with patch("app.routers.site_crawler.crawl_service.check_health", new_callable=AsyncMock) as mock_crawl, \
         patch("app.routers.site_crawler.storage_service.check_health", new_callable=AsyncMock) as mock_storage, \
         patch("app.routers.site_crawler.model_download_manager.check_availability") as mock_avail, \
         patch("app.routers.site_crawler.site_crawler_jobs.create_job", new_callable=AsyncMock) as mock_create, \
         patch("app.routers.site_crawler.site_crawler_jobs.get_status", new_callable=AsyncMock) as mock_status:
        
        mock_crawl.return_value = MagicMock(status="healthy")
        mock_storage.return_value = MagicMock(status="healthy")
        mock_avail.return_value = MagicMock(available=True)
        mock_create.return_value = mock_status_obj
        mock_status.return_value = mock_status_obj

        # Create job (202 Accepted)
        res = client.post("/v1/tools/site-crawler/jobs", json=req_body)
        assert res.status_code == 202
        data = res.json()
        assert data["job_id"] == "job-12345678"
        assert data["slug"] == "docs-run"

        # Get job status (200 OK)
        res_status = client.get("/v1/tools/site-crawler/jobs/job-12345678?bucket=test-bucket")
        assert res_status.status_code == 200
        assert res_status.json()["status"] == "running"


def test_list_projects(client):
    now_iso = datetime.now(timezone.utc).isoformat()
    summaries = [
        ProjectSummary(
            name="Alpha Crawl",
            slug="alpha-crawl",
            bucket="site-crawler",
            created_at=now_iso,
            status="completed",
            counts=JobCounts(total=5, crawled=5, extracted=5, failed=0, records=12),
        )
    ]
    with patch("app.routers.site_crawler.project_store.list_projects", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = summaries
        res = client.get("/v1/tools/site-crawler/projects?bucket=site-crawler")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["slug"] == "alpha-crawl"
        assert data[0]["counts"]["records"] == 12


def test_get_project_detail(client):
    now_iso = datetime.now(timezone.utc).isoformat()
    manifest = ProjectManifest(
        name="Alpha Crawl",
        slug="alpha-crawl",
        bucket="site-crawler",
        job_id="job-abc",
        created_at=now_iso,
        updated_at=now_iso,
        status="completed",
        settings={},
        counts=JobCounts(total=1, crawled=1, extracted=1, failed=0, records=1),
        pages=[PageResult(url="https://example.com", hash="1122334455667788", crawl_status="crawled", extraction_status="ok", record_count=1)],
    )
    schema = ExtractionSchema(
        mode="single",
        fields=[FieldDefinition(name="title", type="string", description="Title", required=True)],
        version=1,
    )
    data_file = DataFile(
        project={"name": "Alpha Crawl", "slug": "alpha-crawl"},
        schema=schema,
        records=[{"title": "Example Title"}],
    )

    with patch("app.routers.site_crawler.project_store.load_manifest", new_callable=AsyncMock) as mock_man, \
         patch("app.routers.site_crawler.project_store.load_schema", new_callable=AsyncMock) as mock_sch, \
         patch("app.routers.site_crawler.project_store.load_data", new_callable=AsyncMock) as mock_dat:
        
        mock_man.return_value = manifest
        mock_sch.return_value = schema
        mock_dat.return_value = data_file

        res = client.get("/v1/tools/site-crawler/projects/alpha-crawl?bucket=site-crawler")
        assert res.status_code == 200
        body = res.json()
        assert body["manifest"]["name"] == "Alpha Crawl"
        assert len(body["records"]) == 1
        assert body["records"][0]["title"] == "Example Title"


def test_get_project_detail_invalid_slug(client):
    res = client.get("/v1/tools/site-crawler/projects/INVALID_SLUG_WITH_CAPS!")
    assert res.status_code == 400


def test_get_project_detail_not_found(client):
    with patch("app.routers.site_crawler.project_store.load_manifest", new_callable=AsyncMock) as mock_man:
        mock_man.return_value = None
        res = client.get("/v1/tools/site-crawler/projects/nonexistent-project")
        assert res.status_code == 404


def test_delete_project(client):
    now_iso = datetime.now(timezone.utc).isoformat()
    manifest = ProjectManifest(
        name="Alpha Crawl",
        slug="alpha-crawl",
        bucket="site-crawler",
        job_id="job-abc",
        created_at=now_iso,
        updated_at=now_iso,
        status="completed",
        settings={},
        counts=JobCounts(),
    )
    with patch("app.routers.site_crawler.project_store.load_manifest", new_callable=AsyncMock) as mock_man, \
         patch("app.routers.site_crawler.project_store.delete_project", new_callable=AsyncMock) as mock_del:
        
        mock_man.return_value = manifest
        mock_del.return_value = None

        res = client.delete("/v1/tools/site-crawler/projects/alpha-crawl?bucket=site-crawler")
        assert res.status_code == 204
        mock_del.assert_awaited_once_with("site-crawler", "alpha-crawl")


def test_delete_running_project_conflict(client):
    now_iso = datetime.now(timezone.utc).isoformat()
    manifest = ProjectManifest(
        name="Running Project",
        slug="running-project",
        bucket="site-crawler",
        job_id="job-abc",
        created_at=now_iso,
        updated_at=now_iso,
        status="running",
        settings={},
        counts=JobCounts(),
    )
    with patch("app.routers.site_crawler.project_store.load_manifest", new_callable=AsyncMock) as mock_man:
        mock_man.return_value = manifest
        res = client.delete("/v1/tools/site-crawler/projects/running-project?bucket=site-crawler")
        assert res.status_code == 409


def test_get_project_page_detail(client):
    page_data = {
        "markdown": "# Header\nContent",
        "meta": {"url": "https://example.com"},
        "records": [{"title": "Header"}],
    }
    with patch("app.routers.site_crawler.project_store.load_page_detail", new_callable=AsyncMock) as mock_page:
        mock_page.return_value = page_data
        res = client.get("/v1/tools/site-crawler/projects/alpha-crawl/pages/0123456789abcdef?bucket=site-crawler")
        assert res.status_code == 200
        assert res.json()["markdown"] == "# Header\nContent"
