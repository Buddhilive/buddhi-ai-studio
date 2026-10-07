from datetime import datetime, timezone
import pytest
from botocore.stub import Stubber

from app.schemas.storage import CreateBucketRequest
from app.services.storage_service import (
    BucketAlreadyExistsError,
    StorageError,
    StorageService,
)


def test_create_bucket_validation():
    # Valid names
    assert CreateBucketRequest(name="my-bucket").name == "my-bucket"
    assert CreateBucketRequest(name="site-crawler-data").name == "site-crawler-data"
    assert CreateBucketRequest(name="bucket123").name == "bucket123"

    # Invalid names
    with pytest.raises(ValueError):
        CreateBucketRequest(name="ab")  # too short
    with pytest.raises(ValueError):
        CreateBucketRequest(name="MyBucket")  # uppercase
    with pytest.raises(ValueError):
        CreateBucketRequest(name="-invalid-start")
    with pytest.raises(ValueError):
        CreateBucketRequest(name="invalid-end-")
    with pytest.raises(ValueError):
        CreateBucketRequest(name="invalid..dots")


@pytest.mark.asyncio
async def test_storage_list_buckets():
    service = StorageService(endpoint_url="http://mock-rustfs:9000")
    client = service._get_sync_client()
    stubber = Stubber(client)

    now = datetime.now(timezone.utc)
    response = {
        "Buckets": [
            {"Name": "test-bucket", "CreationDate": now},
            {"Name": "site-crawler", "CreationDate": now},
        ],
        "Owner": {"DisplayName": "rustfs", "ID": "123"},
    }

    stubber.add_response("list_buckets", response, {})
    with stubber:
        buckets = await service.list_buckets()
        assert len(buckets) == 2
        assert buckets[0].name == "test-bucket"
        assert buckets[1].name == "site-crawler"


@pytest.mark.asyncio
async def test_storage_create_bucket():
    service = StorageService(endpoint_url="http://mock-rustfs:9000")
    client = service._get_sync_client()
    stubber = Stubber(client)

    stubber.add_response("create_bucket", {"Location": "/new-bucket"}, {"Bucket": "new-bucket"})
    with stubber:
        info = await service.create_bucket("new-bucket")
        assert info.name == "new-bucket"


@pytest.mark.asyncio
async def test_storage_put_and_get_json():
    service = StorageService(endpoint_url="http://mock-rustfs:9000")
    client = service._get_sync_client()
    stubber = Stubber(client)

    # Test put_json
    expected_body = b'{\n  "hello": "world"\n}'
    stubber.add_response(
        "put_object",
        {"ETag": '"12345"'},
        {
            "Bucket": "test-b",
            "Key": "sample.json",
            "Body": expected_body,
            "ContentType": "application/json",
        },
    )

    with stubber:
        await service.put_json("test-b", "sample.json", {"hello": "world"})


@pytest.mark.asyncio
async def test_storage_delete_prefix():
    service = StorageService(endpoint_url="http://mock-rustfs:9000")
    client = service._get_sync_client()
    stubber = Stubber(client)

    # 1. list_objects_v2
    stubber.add_response(
        "list_objects_v2",
        {
            "Contents": [
                {"Key": "proj/a.txt"},
                {"Key": "proj/b.txt"},
            ],
            "IsTruncated": False,
        },
        {"Bucket": "test-b", "Prefix": "proj/"},
    )

    # 2. delete_objects
    stubber.add_response(
        "delete_objects",
        {"Deleted": [{"Key": "proj/a.txt"}, {"Key": "proj/b.txt"}]},
        {
            "Bucket": "test-b",
            "Delete": {
                "Objects": [{"Key": "proj/a.txt"}, {"Key": "proj/b.txt"}],
                "Quiet": True,
            },
        },
    )

    with stubber:
        count = await service.delete_prefix("test-b", "proj/")
        assert count == 2
