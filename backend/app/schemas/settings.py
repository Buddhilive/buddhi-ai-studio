from pydantic import BaseModel, field_validator


class HfTokenRequest(BaseModel):
    token: str

    @field_validator("token")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Token must not be empty")
        return trimmed


class HfTokenStatus(BaseModel):
    configured: bool
