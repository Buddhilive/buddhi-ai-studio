"""Tests for the embeddings API endpoint."""

import json
import pytest
from httpx import AsyncClient
from core.main import app


@pytest.mark.asyncio
async def test_empty_string_input():
    """Empty string input should be rejected."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": "",
                "model": "test/model",
            },
        )
        assert response.status_code == 422
        data = response.json()
        assert "error" not in data or "value_error" in data.get("detail", [{}])[0].get("type", "")


@pytest.mark.asyncio
async def test_empty_list_input():
    """Empty list input should be rejected."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": [],
                "model": "test/model",
            },
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_token_array_input_single():
    """Single token array should be rejected."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": [1, 2, 3, 4],
                "model": "test/model",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "Token array input not supported" in data["detail"]["error"]["message"]


@pytest.mark.asyncio
async def test_token_batch_input():
    """Batch of token arrays should be rejected."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": [[1, 2], [3, 4]],
                "model": "test/model",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "not supported" in data["detail"]["error"]["message"].lower()


@pytest.mark.asyncio
async def test_unknown_model():
    """Unknown model should return 404."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": "test text",
                "model": "unknown/nonexistent-model-xyz",
            },
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "model_not_found"


@pytest.mark.asyncio
async def test_single_string_input_structure():
    """Valid request should have correct response structure (even if model doesn't load)."""
    # This test verifies the request reaches the service layer
    # Actual success depends on having a loadable model
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": "test text",
                "model": "unknown/model",
            },
        )
        # Should fail at model lookup, not at schema validation
        data = response.json()
        assert "error" in data["detail"]


@pytest.mark.asyncio
async def test_batch_string_input_structure():
    """Valid batch request should be accepted (model lookup is next step)."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": ["hello", "world"],
                "model": "unknown/model",
            },
        )
        # Should fail at model lookup, not at schema validation
        data = response.json()
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "model_not_found"


@pytest.mark.asyncio
async def test_encoding_format_float():
    """Float encoding format should be accepted."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": "test",
                "model": "unknown/model",
                "encoding_format": "float",
            },
        )
        # Should fail at model lookup, not at encoding format
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_encoding_format_base64():
    """Base64 encoding format should be accepted."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": "test",
                "model": "unknown/model",
                "encoding_format": "base64",
            },
        )
        # Should fail at model lookup, not at encoding format
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_dimensions_parameter():
    """Dimensions parameter should be accepted."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": "test",
                "model": "unknown/model",
                "dimensions": 256,
            },
        )
        # Should fail at model lookup, not at dimensions
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_dimensions():
    """Negative dimensions should be rejected."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": "test",
                "model": "test/model",
                "dimensions": -1,
            },
        )
        # Should fail validation
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_user_parameter():
    """User parameter should be accepted (optional)."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": "test",
                "model": "unknown/model",
                "user": "test-user-123",
            },
        )
        # Should fail at model lookup, not at user parameter
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_response_structure():
    """Response should have OpenAI-compatible structure (even on error)."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": "test",
                "model": "unknown/model",
            },
        )
        data = response.json()
        # Error response
        assert "error" in data["detail"]
        assert "message" in data["detail"]["error"]
        assert "code" in data["detail"]["error"]
        assert "type" in data["detail"]["error"]


@pytest.mark.asyncio
async def test_empty_string_in_batch():
    """Empty string in batch should be rejected."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": ["hello", "", "world"],
                "model": "test/model",
            },
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_mixed_types_in_batch():
    """Mixed types in batch should be rejected."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={
                "input": ["hello", 123, "world"],
                "model": "test/model",
            },
        )
        # Pydantic should reject this
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
