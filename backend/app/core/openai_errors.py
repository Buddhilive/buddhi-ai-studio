from __future__ import annotations

from fastapi import HTTPException


def openai_error(
    status_code: int, message: str, error_type: str, param: str | None = None
) -> HTTPException:
    """Builds an HTTPException whose `.detail` matches OpenAI's error envelope.

    `main.py`'s `/v1/*` exception handlers pass a dict `detail` with an
    "error" key straight through as the JSON body, so raising this gives an
    OpenAI-compatible error response for free.
    """
    return HTTPException(
        status_code=status_code,
        detail={"error": {"message": message, "type": error_type, "param": param, "code": None}},
    )
