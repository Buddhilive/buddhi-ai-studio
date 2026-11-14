from fastapi import APIRouter, HTTPException

from app.core import settings_store
from app.schemas.settings import (
    EgmSettings,
    HarnessSettings,
    HfTokenRequest,
    HfTokenStatus,
    InferenceSettings,
    RlmSettings,
    RlmSettingsResponse,
    SystemResourceRecommendation,
)
from app.services.inference_service import inference_engine_manager
from app.services.rlm.reach import compute_effective_reach
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
def get_system_resources(model_id: str | None = None) -> SystemResourceRecommendation:
    return get_system_resource_recommendation(model_id=model_id)


@router.get("/rlm", response_model=RlmSettingsResponse)
def get_rlm_settings() -> RlmSettingsResponse:
    conf = settings_store.get_rlm_settings()
    inf_conf = settings_store.get_inference_settings()
    context_window = int(inf_conf.get("max_num_token", 16384))

    reach = compute_effective_reach(
        context_window=context_window,
        snippet_tokens=conf.get("snippet_tokens", 2048),
        max_depth=conf.get("max_depth", 2),
        max_subcalls=conf.get("max_subcalls", 32),
        prompt_reserve_tokens=conf.get("prompt_reserve_tokens", 2048),
    )

    return RlmSettingsResponse(
        enabled=conf.get("enabled", True),
        mode=conf.get("mode", "auto"),
        max_depth=conf.get("max_depth", 2),
        snippet_tokens=conf.get("snippet_tokens", 2048),
        max_subcalls=conf.get("max_subcalls", 32),
        subcall_concurrency=conf.get("subcall_concurrency", 2),
        auto_threshold_ratio=conf.get("auto_threshold_ratio", 0.6),
        prompt_reserve_tokens=conf.get("prompt_reserve_tokens", 2048),
        effective_reach_tokens=reach.effective_reach_tokens,
        fan_out=reach.fan_out,
        bounded_by_budget=reach.bounded_by_budget,
    )


@router.put("/rlm", response_model=RlmSettingsResponse)
def update_rlm_settings(request: RlmSettings) -> RlmSettingsResponse:
    settings_store.set_rlm_settings(request.model_dump())
    return get_rlm_settings()


@router.get("/egm", response_model=EgmSettings)
def get_egm_settings_api() -> EgmSettings:
    data = settings_store.get_egm_settings()
    return EgmSettings(**data)


@router.put("/egm", response_model=EgmSettings)
def update_egm_settings_api(request: EgmSettings) -> EgmSettings:
    settings_store.set_egm_settings(request.model_dump())
    return request


@router.get("/harness", response_model=HarnessSettings)
def get_harness_settings_api() -> HarnessSettings:
    return HarnessSettings(**settings_store.get_harness_settings())


@router.put("/harness", response_model=HarnessSettings)
def update_harness_settings_api(request: HarnessSettings) -> HarnessSettings:
    settings_store.set_harness_settings(request.model_dump())
    return request


