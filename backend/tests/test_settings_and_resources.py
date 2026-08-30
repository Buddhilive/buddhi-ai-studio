import pytest
from fastapi.testclient import TestClient

from app.core import settings_store
from app.main import app
from app.services.inference_service import inference_engine_manager


@pytest.fixture(autouse=True)
def reset_settings():
    yield
    # Reset to defaults
    settings_store.set_inference_settings("cpu", 16384)
    inference_engine_manager.reconfigure("cpu", 16384)


def test_get_and_put_inference_settings():
    client = TestClient(app)

    # Initial GET
    res = client.get("/api/settings/inference")
    assert res.status_code == 200
    data = res.json()
    assert "litert_backend" in data
    assert "max_num_token" in data

    # Update settings
    put_res = client.put(
        "/api/settings/inference",
        json={"litert_backend": "gpu", "max_num_token": 8192},
    )
    assert put_res.status_code == 200
    updated_data = put_res.json()
    assert updated_data["litert_backend"] == "gpu"
    assert updated_data["max_num_token"] == 8192

    # Verify GET reflects update
    res2 = client.get("/api/settings/inference")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["litert_backend"] == "gpu"
    assert data2["max_num_token"] == 8192

    # Verify engine manager has been reconfigured
    assert inference_engine_manager.get_current_backend() == "gpu"
    assert inference_engine_manager.get_current_max_tokens() == 8192


def test_inference_settings_validation():
    client = TestClient(app)

    # Invalid token count (too low)
    res = client.put(
        "/api/settings/inference",
        json={"litert_backend": "cpu", "max_num_token": 100},
    )
    assert res.status_code == 422

    # Invalid backend option
    res_bad_backend = client.put(
        "/api/settings/inference",
        json={"litert_backend": "invalid_backend", "max_num_token": 4096},
    )
    assert res_bad_backend.status_code == 422


def test_get_system_resources():
    client = TestClient(app)
    res = client.get("/api/settings/system-resources")
    assert res.status_code == 200
    data = res.json()

    assert "total_memory_bytes" in data
    assert data["total_memory_bytes"] > 0
    assert "available_memory_bytes" in data
    assert data["available_memory_bytes"] > 0
    assert "cpu_count" in data
    assert data["cpu_count"] >= 1

    assert "supported_backends" in data
    backends = {b["id"]: b for b in data["supported_backends"]}
    assert "cpu" in backends
    assert backends["cpu"]["supported"] is True

    assert "gpu" in backends
    assert "npu" in backends

    assert "recommended_backend" in data
    assert data["recommended_backend"] in ["cpu", "gpu", "npu"]

    assert "recommended_max_num_tokens" in data
    assert data["recommended_max_num_tokens"] in [2048, 4096, 8192, 16384, 32768]

    assert "max_viable_tokens" in data
    assert data["max_viable_tokens"] >= data["recommended_max_num_tokens"]

    assert "reasoning" in data
    assert len(data["reasoning"]) > 0

