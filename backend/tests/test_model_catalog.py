from fastapi.testclient import TestClient

from app.core.model_catalog import MODEL_CATALOG, ModelCategory
from app.main import app


def test_model_catalog_contains_only_gemma_4_llms():
    llm_entries = [m for m in MODEL_CATALOG if m.category == ModelCategory.LLM]
    llm_ids = [m.id for m in llm_entries]
    assert sorted(llm_ids) == ["gemma-4-e2b", "gemma-4-e4b"]
    for entry in llm_entries:
        assert entry.name in ["Gemma 4 E2B", "Gemma 4 E4B"]


def test_model_catalog_retains_embedding_models():
    embedding_entries = [m for m in MODEL_CATALOG if m.category == ModelCategory.EMBEDDING]
    embedding_ids = [m.id for m in embedding_entries]
    assert "embeddinggemma-300m-litert" in embedding_ids
    assert "embeddinggemma-300m-tokenizer" in embedding_ids


def test_v1_models_endpoint_does_not_return_embeddings():
    client = TestClient(app)
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    returned_ids = [m["id"] for m in data["data"]]
    # Strictly ensure no embedding models are present
    assert "embeddinggemma-300m" not in returned_ids
    assert "embeddinggemma-300m-litert" not in returned_ids
    assert "embeddinggemma-300m-tokenizer" not in returned_ids
    # Any returned models must only be gemma-4 LLMs
    for model_id in returned_ids:
        assert model_id in ["gemma-4-e4b", "gemma-4-e2b"]
