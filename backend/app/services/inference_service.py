from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import re
import threading
from collections.abc import Mapping

from litert_lm import Backend, Content, Contents, Engine

from app.core.config import settings
from app.schemas.chat import ChatCompletionChunkDelta, ChatMessage
from app.services.model_download_service import model_download_manager

logger = logging.getLogger(__name__)

_BACKENDS = {
    "cpu": Backend.CPU,
    "gpu": Backend.GPU,
    "npu": Backend.NPU,
}

# litert_lm's Message/Role enum uses "model" for prior assistant turns; only
# its *response* dicts are labeled "assistant" (see litert_lm.interfaces
# Conversation.send_message docstring). Raw dict messages are passed through
# verbatim, so history we replay has to speak the engine's role vocabulary.
_ROLE_TO_ENGINE = {"system": "system", "user": "user", "assistant": "model"}


class ModelNotAvailableError(RuntimeError):
    """Raised when the model file has not been downloaded yet."""


class InferenceError(RuntimeError):
    """Raised when the LiteRT-LM engine fails to generate a response."""


def _extract_text(response: Mapping) -> str:
    parts = response.get("content", [])
    if isinstance(parts, str):
        return parts
    if not isinstance(parts, list):
        return ""
    return "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("type") == "text"
    )


_DATA_URL_RE = re.compile(r"^data:[^;,]*;base64,(.*)$", re.DOTALL)


def _decode_image_url(url: str) -> bytes:
    match = _DATA_URL_RE.match(url)
    if not match:
        raise InferenceError(
            "Image attachments must be base64 data URLs (data:<mime>;base64,<data>)."
        )
    try:
        return base64.b64decode(match.group(1), validate=True)
    except binascii.Error as exc:
        raise InferenceError(f"Invalid base64 image data: {exc}") from exc


def _content_to_engine_message(content: str | list) -> str | Contents:
    """Converts a ChatMessage.content into what Conversation.send_message expects."""
    if isinstance(content, str):
        return content
    parts: list = []
    for part in content:
        if part.type == "text":
            parts.append(Content.Text(part.text))
        elif part.type == "image_url":
            parts.append(Content.ImageBytes(_decode_image_url(part.image_url.url)))
    return Contents.of(*parts) if parts else Contents.empty()


def _content_to_text(content: str | list) -> str:
    """Flattens a ChatMessage.content to plain text (history replay, token counting)."""
    if isinstance(content, str):
        return content
    return "".join(part.text for part in content if part.type == "text")


class InferenceEngineManager:
    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._load_lock = threading.Lock()
        self._generate_lock = asyncio.Lock()

    def _load_engine(self) -> Engine:
        if self._engine is not None:
            return self._engine
        with self._load_lock:
            if self._engine is not None:
                return self._engine
            availability = model_download_manager.check_availability()
            if not availability.available or not availability.path:
                raise ModelNotAvailableError(
                    "Model is not downloaded yet. Start a download via /api/models/download."
                )
            backend_cls = _BACKENDS.get(settings.litert_backend, Backend.CPU)
            try:
                self._engine = Engine(
                    availability.path, backend=backend_cls(), vision_backend=backend_cls()
                )
            except Exception as exc:  # pragma: no cover - depends on native runtime
                raise InferenceError(f"Failed to load LiteRT-LM engine: {exc}") from exc
            return self._engine

    def warm_up(self) -> None:
        try:
            self._load_engine()
        except ModelNotAvailableError:
            logger.info("Skipping inference engine warm-up: model not downloaded yet.")
        except InferenceError as exc:
            logger.warning("Inference engine warm-up failed: %s", exc)

    @staticmethod
    def _split_history(messages: list[ChatMessage]) -> tuple[str | None, list[dict], ChatMessage]:
        """Splits messages into (system_message, prior_history, last_message)."""
        system_message: str | None = None
        rest = list(messages)
        if rest and rest[0].role == "system":
            system_message = _content_to_text(rest[0].content)
            rest = rest[1:]
        if not rest:
            raise InferenceError("At least one user message is required after the system message.")
        *history, last = rest
        history_dicts = [
            {"role": _ROLE_TO_ENGINE[m.role], "content": _content_to_text(m.content)} for m in history
        ]
        return system_message, history_dicts, last

    def _create_conversation(self, engine: Engine, messages: list[ChatMessage]):
        system_message, history, last = self._split_history(messages)
        conversation = engine.create_conversation(
            messages=history or None, system_message=system_message
        )
        return conversation, last

    def _token_count(self, engine: Engine, text: str) -> int:
        try:
            return len(engine.tokenize(text))
        except Exception:  # pragma: no cover - defensive fallback
            return max(1, len(text.split()))

    async def generate(self, messages: list[ChatMessage], max_tokens: int | None) -> tuple[str, int, int]:
        engine = self._load_engine()
        effective_max_tokens = max_tokens or settings.chat_max_tokens_default

        def _run() -> str:
            conversation, last_message = self._create_conversation(engine, messages)
            response = conversation.send_message(
                _content_to_engine_message(last_message.content), max_output_tokens=effective_max_tokens
            )
            return _extract_text(response)

        async with self._generate_lock:
            try:
                text = await asyncio.to_thread(_run)
            except (ModelNotAvailableError, InferenceError):
                raise
            except Exception as exc:
                raise InferenceError(f"Generation failed: {exc}") from exc

        prompt_text = "\n".join(_content_to_text(m.content) for m in messages)
        prompt_tokens = self._token_count(engine, prompt_text)
        completion_tokens = self._token_count(engine, text)
        return text, prompt_tokens, completion_tokens

    async def generate_stream(self, messages: list[ChatMessage], max_tokens: int | None):
        engine = self._load_engine()
        effective_max_tokens = max_tokens or settings.chat_max_tokens_default

        def _make_iterator():
            conversation, last_message = self._create_conversation(engine, messages)
            return conversation.send_message_async(
                _content_to_engine_message(last_message.content), max_output_tokens=effective_max_tokens
            )

        async with self._generate_lock:
            try:
                iterator = await asyncio.to_thread(_make_iterator)
                sync_iterator = iter(iterator)
                while True:
                    try:
                        chunk = await asyncio.to_thread(next, sync_iterator)
                    except StopIteration:
                        break
                    text = _extract_text(chunk)
                    if text:
                        yield ChatCompletionChunkDelta(content=text)
            except (ModelNotAvailableError, InferenceError):
                raise
            except Exception as exc:
                raise InferenceError(f"Streaming generation failed: {exc}") from exc


inference_engine_manager = InferenceEngineManager()
