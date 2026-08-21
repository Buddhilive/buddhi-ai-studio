from fastapi import APIRouter

from app.core import settings_store
from app.schemas.settings import HfTokenRequest, HfTokenStatus

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
