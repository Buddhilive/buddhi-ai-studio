from fastapi.testclient import TestClient
from app.main import app


def test_get_and_put_rlm_settings():
    client = TestClient(app)

    # Initial GET
    res = client.get("/api/settings/rlm")
    assert res.status_code == 200
    data = res.json()
    assert "enabled" in data
    assert "max_depth" in data
    assert "effective_reach_tokens" in data
    assert "fan_out" in data

    # Update RLM settings
    put_res = client.put(
        "/api/settings/rlm",
        json={
            "enabled": True,
            "mode": "always",
            "max_depth": 3,
            "snippet_tokens": 1024,
            "max_subcalls": 64,
            "subcall_concurrency": 2,
            "auto_threshold_ratio": 0.5,
            "prompt_reserve_tokens": 2048,
        },
    )
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["mode"] == "always"
    assert updated["max_depth"] == 3
    assert updated["snippet_tokens"] == 1024
    assert updated["max_subcalls"] == 64
    assert updated["effective_reach_tokens"] > 0
