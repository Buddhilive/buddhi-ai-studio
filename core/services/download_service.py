"""Ollama model pull service — replaces the previous HuggingFace download service."""

import json
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

# In-memory store for active/completed pulls
pull_store: dict[str, "PullEntry"] = {}


@dataclass
class PullEntry:
    """State for a single Ollama model pull."""

    id: str          # sanitized model name, e.g. "qwen3.5_3b"
    model: str       # Ollama model name, e.g. "qwen3.5:3b"
    name: str        # display name
    status: str      # pending | pulling | completed | failed
    percentage: int  # 0-100
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to the ModelRecord shape expected by the frontend."""
        tag = self.model.split(":")[-1] if ":" in self.model else ""
        return {
            "id": self.id,
            "model_id": self.model,
            "name": self.name,
            "quantization": tag,
            "status": self.status,
            "progress": self.percentage,
            "path": None,
            "error": self.error,
        }


def sanitize_id(model: str) -> str:
    """Convert an Ollama model name to a safe dictionary key."""
    return model.replace(":", "_").replace("/", "_")


# ── Ollama API helpers ────────────────────────────────────────────────────────

def get_ollama_models() -> list[dict]:
    """
    Fetch list of installed models from Ollama.
    Returns list of dicts with at least 'name' key.
    Returns empty list if Ollama is unreachable.
    """
    try:
        resp = httpx.get(
            f"{settings.ollama_base_url}/api/tags",
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("models", [])
    except Exception as e:
        logger.warning(f"Could not fetch Ollama models: {e}")
        return []


def delete_ollama_model(model: str) -> None:
    """
    Delete a model from Ollama.
    Raises httpx.HTTPError on failure.
    """
    resp = httpx.request(
        "DELETE",
        f"{settings.ollama_base_url}/api/delete",
        json={"name": model},
        timeout=30,
    )
    resp.raise_for_status()
    logger.info(f"Deleted Ollama model: {model}")


# ── Startup scan ─────────────────────────────────────────────────────────────

def scan_installed_models() -> None:
    """
    Populate pull_store from Ollama's installed model list at startup.
    Existing in-progress entries are not overwritten.
    """
    global pull_store
    models = get_ollama_models()
    for m in models:
        name = m.get("name", "")
        if not name:
            continue
        entry_id = sanitize_id(name)
        if entry_id not in pull_store:
            pull_store[entry_id] = PullEntry(
                id=entry_id,
                model=name,
                name=name.split(":")[0],
                status="completed",
                percentage=100,
            )
    logger.info(f"Loaded {len(models)} installed Ollama model(s) into pull_store")


# ── Background pull task ──────────────────────────────────────────────────────

def do_pull(model: str) -> None:
    """
    Pull a model from Ollama with live progress tracking.

    Runs as a background task (blocking). Updates pull_store entry in real time.
    Ollama streams NDJSON lines:
        {"status":"pulling manifest"}
        {"status":"pulling ...","total":1234567,"completed":500000}
        {"status":"success"}
    """
    entry_id = sanitize_id(model)
    entry = pull_store.get(entry_id)
    if not entry:
        logger.error(f"Pull entry not found for {model}")
        return

    try:
        logger.info(f"Starting Ollama pull: {model}")
        entry.status = "pulling"

        with httpx.stream(
            "POST",
            f"{settings.ollama_base_url}/api/pull",
            json={"name": model, "stream": True},
            timeout=httpx.Timeout(connect=30.0, read=None, write=None, pool=None),
        ) as resp:
            if resp.status_code == 404:
                entry.status = "failed"
                entry.error = f"Model '{model}' not found in Ollama registry"
                return
            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                status = data.get("status", "")

                if status == "success":
                    entry.status = "completed"
                    entry.percentage = 100
                    logger.info(f"Ollama pull completed: {model}")
                    return

                total = data.get("total", 0)
                completed = data.get("completed", 0)
                if total and completed:
                    entry.percentage = min(99, int(completed / total * 100))

                if "error" in data:
                    entry.status = "failed"
                    entry.error = data["error"]
                    logger.error(f"Ollama pull error for {model}: {data['error']}")
                    return

        # If stream ended without success
        if entry.status != "completed":
            entry.status = "failed"
            entry.error = "Pull stream ended without success"

    except httpx.HTTPStatusError as e:
        entry.status = "failed"
        entry.error = f"Ollama API error: HTTP {e.response.status_code}"
        logger.error(entry.error)
    except Exception as e:
        entry.status = "failed"
        entry.error = f"Pull failed: {e}"
        logger.error(entry.error, exc_info=True)
