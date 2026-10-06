import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.site_crawler import (
    CrawlOptions,
    CreateJobRequest,
    ExtractionSchema,
    FieldDefinition,
    ProjectManifest,
)
from app.services.site_crawler.jobs import SiteCrawlerJobManager
from app.services.site_crawler.project_store import (
    ProjectExistsError,
    ProjectStore,
    slugify,
    url_hash,
)


def test_slugify():
    assert slugify("My New Project!") == "my-new-project"
    assert slugify("___test_123___") == "test-123"
    assert slugify("   ") == "project"
    assert slugify("A" * 100) == "a" * 64


def test_url_hash():
    h1 = url_hash("https://example.com/page1")
    h2 = url_hash("https://example.com/page2")
    assert len(h1) == 16
    assert h1 != h2
    assert h1 == url_hash("https://example.com/page1")


@pytest.mark.asyncio
async def test_project_store_create_collision():
    store = ProjectStore()
    schema = ExtractionSchema(
        mode="single",
        fields=[FieldDefinition(name="title", type="string")],
    )

    with patch("app.services.site_crawler.project_store.storage_service.exists", AsyncMock(return_value=True)):
        with pytest.raises(ProjectExistsError):
            await store.create_project(
                bucket="test-b",
                project_name="Duplicate Name",
                schema=schema,
                settings_dict={},
                urls=["https://example.com"],
            )


@pytest.mark.asyncio
async def test_job_manager_lifecycle():
    manager = SiteCrawlerJobManager()
    schema = ExtractionSchema(
        mode="single",
        fields=[FieldDefinition(name="title", type="string", required=True)],
    )

    req = CreateJobRequest(
        project_name="Unit Test Job",
        bucket="test-b",
        urls=["https://example.com/p1", "https://example.com/p2"],
        schema=schema,
        max_pages=10,
    )

    with patch("app.services.site_crawler.jobs.storage_service.ensure_bucket", AsyncMock()):
        with patch("app.services.site_crawler.jobs.project_store.create_project") as mock_create:
            mock_manifest = ProjectManifest(
                name="Unit Test Job",
                slug="unit-test-job",
                bucket="test-b",
                job_id="test-job-uuid",
                created_at="2026-10-06T00:00:00Z",
                updated_at="2026-10-06T00:00:00Z",
                status="queued",
                pages=[],
            )
            mock_create.return_value = mock_manifest

            # Intercept runner.run to avoid actual network/LLM in unit test
            with patch("app.services.site_crawler.jobs.JobRunner.run", AsyncMock()):
                status = await manager.create_job(req)
                assert status.job_id == "test-job-uuid"
                assert status.status == "queued"
                assert status.slug == "unit-test-job"

                # Check get_status
                retrieved = await manager.get_status("test-job-uuid")
                assert retrieved is not None
                assert retrieved.job_id == "test-job-uuid"

                # Check cancel
                canceled = await manager.cancel("test-job-uuid")
                assert canceled is not None
