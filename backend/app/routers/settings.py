from fastapi import APIRouter

from app.core import settings_store
from app.schemas.settings import (
    HfTokenRequest,
    HfTokenStatus,
    InferenceSettings,
    SystemResourceRecommendation,
)
from app.services.inference_service import inference_engine_manager
from app.services.system_resource_service import get_system_resource_recommendation

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/hf-token", response_model=HfTokenStatus)
def get_hf_token_status() -> HfTokenStatus:
    return HfTokenStatus(configured=settings_store.get_hf_token() is not None)


@router.put("/hf-token", response_model=HfTokenStatus)
def set_hf_token(request: HfTokenRequest) -> HfTokenStatus:
    settings_store.set_hf_token(request.token)
    return HfTokenStatus(configured=True)


@router.delete("/hf-token", response_model=HfTokenStatus)
def delete_hf_token() -> HfTokenStatus:
    settings_store.clear_hf_token()
    return HfTokenStatus(configured=False)


@router.get("/inference", response_model=InferenceSettings)
def get_inference_settings() -> InferenceSettings:
    data = settings_store.get_inference_settings()
    return InferenceSettings(
        litert_backend=data["litert_backend"],
        max_num_token=data["max_num_token"],
    )


@router.put("/inference", response_model=InferenceSettings)
def update_inference_settings(request: InferenceSettings) -> InferenceSettings:
    settings_store.set_inference_settings(request.litert_backend, request.max_num_token)
    inference_engine_manager.reconfigure(request.litert_backend, request.max_num_token)
    return request


@router.get("/system-resources", response_model=SystemResourceRecommendation)
def get_system_resources() -> SystemResourceRecommendation:
    return get_system_resource_recommendation()


