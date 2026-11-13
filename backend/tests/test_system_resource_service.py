from app.services.system_resource_service import get_system_resource_recommendation


def test_system_resource_recommendation_e4b():
    rec = get_system_resource_recommendation(model_id="gemma-4-e4b")
    assert rec.model_assumed == "Gemma 4 E4B"
    assert rec.max_viable_tokens >= 2048
    assert rec.recommended_max_num_tokens >= 2048
    assert "Gemma 4 E4B" in rec.reasoning


def test_system_resource_recommendation_e2b():
    rec = get_system_resource_recommendation(model_id="gemma-4-e2b")
    assert rec.model_assumed == "Gemma 4 E2B"
    assert rec.max_viable_tokens >= 2048
    assert "Gemma 4 E2B" in rec.reasoning
