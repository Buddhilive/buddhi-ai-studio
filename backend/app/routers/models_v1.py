from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, status

from app.core import model_metadata_store
from app.core.config import settings
from app.core.model_catalog import MODEL_CATALOG
from app.core.openai_errors import openai_error
from app.schemas.models import ModelListResponse, ModelObject
from app.services.embedding_service import EmbeddingStatus, embedding_engine_manager
from app.services.model_download_service import model_download_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["models"])

_OWNED_BY = "buddhi-ai-studio"


def _get_or_backfill_created(model_id: str, source_path: Path) -> int | None:
    created = model_metadata_store.get_created(model_id)
    if created is not None:
        return created
    try:
        created = int(source_path.stat().st_mtime)
    except OSError:
        logger.warning("Could not stat '%s' for model '%s'", source_path, model_id, exc_info=True)
        return None
    model_metadata_store.record_created(model_id, created)
    return created


def _llm_models() -> list[ModelObject]:
    models: list[ModelObject] = []
    for entry in MODEL_CATALOG:
        availability = model_download_manager.check_availability(entry.id)
        if not availability.available or not availability.path:
            continue
        created = _get_or_backfill_created(entry.id, Path(availability.path))
        if created is None:
            continue
        models.append(ModelObject(id=entry.id, created=created, owned_by=_OWNED_BY))
    return models


def _embedding_model() -> ModelObject | None:
    embedding_status, _ = embedding_engine_manager.get_status()
    if embedding_status != EmbeddingStatus.READY:
        return None
    created = _get_or_backfill_created(settings.embedding_model_id, settings.embedding_cache_dir)
    if created is None:
        return None
    return ModelObject(id=settings.embedding_model_id, created=created, owned_by=_OWNED_BY)


@router.get("/models", response_model=ModelListResponse)
def list_models() -> ModelListResponse:
    try:
        models = _llm_models()
        embedding_model = _embedding_model()
        if embedding_model is not None:
            models.append(embedding_model)
    except Exception as exc:  # pragma: no cover - defensive catch-all
        logger.exception("Unexpected error while listing models")
        raise openai_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "An internal error occurred.", "server_error"
        ) from exc

    return ModelListResponse(data=models)
