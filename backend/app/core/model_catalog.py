from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ModelCategory(str, Enum):
    LLM = "llm"
    EMBEDDING = "embedding"


class ModelCatalogEntry(BaseModel):
    id: str
    category: ModelCategory
    name: str
    repo_id: str
    filename: str
    size_bytes: int | None = None


MODEL_CATALOG: list[ModelCatalogEntry] = [
    ModelCatalogEntry(
        id="gemma-4-e4b",
        category=ModelCategory.LLM,
        name="Gemma 4 E4B",
        repo_id="litert-community/gemma-4-E4B-it-litert-lm",
        filename="gemma-4-E4B-it.litertlm",
        size_bytes=3_660_000_000,
    ),
    ModelCatalogEntry(
        id="gemma-4-e2b",
        category=ModelCategory.LLM,
        name="Gemma 4 E2B",
        repo_id="litert-community/gemma-4-E2B-it-litert-lm",
        filename="gemma-4-E2B-it.litertlm",
        size_bytes=2_590_000_000,
    ),
    ModelCatalogEntry(
        id="gemma-3n-e2b",
        category=ModelCategory.LLM,
        name="Gemma 3n E2B",
        repo_id="google/gemma-3n-E2B-it-litert-lm",
        filename="gemma-3n-E2B-it-int4.litertlm",
        size_bytes=3_660_000_000,
    ),
    ModelCatalogEntry(
        id="gemma-3n-e4b",
        category=ModelCategory.LLM,
        name="Gemma 3n E4B",
        repo_id="google/gemma-3n-E4B-it-litert-lm",
        filename="gemma-3n-E4B-it-int4.litertlm",
        size_bytes=4_920_000_000,
    ),
    ModelCatalogEntry(
        id="gemma-3-1b",
        category=ModelCategory.LLM,
        name="Gemma 3 1B IT",
        repo_id="litert-community/Gemma3-1B-IT",
        filename="gemma3-1b-it-int4.litertlm",
        size_bytes=584_000_000,
    ),
]

_CATALOG_BY_ID: dict[str, ModelCatalogEntry] = {entry.id: entry for entry in MODEL_CATALOG}

DEFAULT_CHAT_MODEL_ID = "gemma-4-e4b"


def get_catalog_entry(model_id: str) -> ModelCatalogEntry:
    try:
        return _CATALOG_BY_ID[model_id]
    except KeyError as exc:
        raise KeyError(f"Unknown model id: {model_id}") from exc
