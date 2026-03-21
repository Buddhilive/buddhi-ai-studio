import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from huggingface_hub import hf_hub_download, list_repo_files
from huggingface_hub.errors import (
    RepositoryNotFoundError,
    GatedRepoError,
    HfHubHTTPError,
)

logger = logging.getLogger(__name__)

# Global download store (in-memory)
download_store: dict[str, "DownloadEntry"] = {}

# Models directory
MODELS_DIR = Path(os.getenv("HF_MODELS_DIR", "./data/models"))


@dataclass
class DownloadEntry:
    """State for a single model download."""

    id: str  # sanitized repo_id (e.g., "unsloth_Qwen3.5-0.8B-GGUF")
    repo_id: str  # original HF repo ID (e.g., "unsloth/Qwen3.5-0.8B-GGUF")
    name: str  # display name (derived from repo_id)
    quantization: str  # e.g., "Q4_K_M"
    status: str  # pending | downloading | completed | failed | corrupted
    percentage: int  # 0-100
    path: Optional[str] = None  # absolute path to final .gguf file
    filename: Optional[str] = None  # just the filename
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "id": self.id,
            "model_id": self.repo_id,
            "name": self.name,
            "quantization": self.quantization,
            "status": self.status,
            "progress": self.percentage,
            "path": self.path,
            "error": self.error,
        }


def sanitize_id(repo_id: str) -> str:
    """Convert repo_id to a safe dictionary key."""
    return repo_id.replace("/", "_")


def get_model_path(repo_id: str) -> Optional[str]:
    """
    Get the local path to a completed model if it exists and is verified.
    Returns None if not found, not completed, or .verified sidecar is missing.
    """
    entry = download_store.get(sanitize_id(repo_id))
    if not entry or entry.status != "completed" or not entry.path:
        return None

    # Verify sidecar exists
    verified_path = Path(entry.path).with_suffix(Path(entry.path).suffix + ".verified")
    if not verified_path.exists():
        logger.warning(f"Model {repo_id} marked completed but .verified sidecar missing: {verified_path}")
        entry.status = "corrupted"
        entry.error = "Missing verification sidecar"
        return None

    return entry.path


def scan_models_dir() -> None:
    """
    Scan ./models directory at startup.
    Rebuild download_store from .gguf files and their .verified sidecars.
    """
    global download_store
    download_store.clear()

    if not MODELS_DIR.exists():
        logger.info(f"Models directory does not exist yet: {MODELS_DIR}")
        return

    gguf_files = list(MODELS_DIR.glob("*.gguf"))
    logger.info(f"Found {len(gguf_files)} .gguf files in {MODELS_DIR}")

    for gguf_path in gguf_files:
        verified_path = gguf_path.with_suffix(gguf_path.suffix + ".verified")

        if verified_path.exists():
            try:
                with open(verified_path, "r") as f:
                    metadata = json.load(f)
                repo_id = metadata.get("repo_id")
                quantization = metadata.get("quantization", "unknown")
                filename = metadata.get("filename", gguf_path.name)

                if not repo_id:
                    logger.warning(f"Invalid .verified file (no repo_id): {verified_path}")
                    continue

                entry = DownloadEntry(
                    id=sanitize_id(repo_id),
                    repo_id=repo_id,
                    name=repo_id.split("/")[-1],
                    quantization=quantization,
                    status="completed",
                    percentage=100,
                    path=str(gguf_path),
                    filename=filename,
                    error=None,
                )
                download_store[entry.id] = entry
                logger.info(f"Loaded verified model: {repo_id} ({quantization})")
            except Exception as e:
                logger.error(f"Failed to load .verified file {verified_path}: {e}")
        else:
            # .gguf exists but no .verified sidecar
            logger.warning(f"Found orphaned .gguf file (no .verified sidecar): {gguf_path}")
            # Try to infer repo_id from filename
            filename_base = gguf_path.stem
            entry = DownloadEntry(
                id=sanitize_id(filename_base),
                repo_id=filename_base,
                name=filename_base,
                quantization="unknown",
                status="corrupted",
                percentage=0,
                path=str(gguf_path),
                filename=gguf_path.name,
                error="Missing verification sidecar; file may be incomplete",
            )
            download_store[entry.id] = entry


def _find_gguf_filename(repo_id: str, quantization: str) -> str:
    """
    List files in HF repo and find the best .gguf match.
    Prefer filename matching the quantization string (case-insensitive).
    Falls back to first .gguf if no quantization match.
    """
    try:
        files = list(list_repo_files(repo_id=repo_id, repo_type="model"))
        gguf_files = [f for f in files if f.endswith(".gguf")]

        if not gguf_files:
            raise ValueError(f"No .gguf files found in {repo_id}")

        # Try to match quantization (case-insensitive)
        quantization_lower = quantization.lower()
        for filename in gguf_files:
            if quantization_lower in filename.lower():
                logger.info(f"Found {quantization} match: {filename}")
                return filename

        # Fallback: use first .gguf
        logger.warning(f"No {quantization} match found; using first .gguf: {gguf_files[0]}")
        return gguf_files[0]
    except Exception as e:
        logger.error(f"Failed to list files for {repo_id}: {e}")
        raise


def _get_expected_size(repo_id: str, filename: str, hf_token: Optional[str]) -> Optional[int]:
    """
    Get the Content-Length of a file from HuggingFace without downloading.
    """
    url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
    headers = {}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    try:
        response = httpx.head(url, headers=headers, follow_redirects=True, timeout=10)
        if response.status_code == 200:
            content_length = response.headers.get("content-length")
            if content_length:
                return int(content_length)
    except Exception as e:
        logger.warning(f"Failed to get size for {filename}: {e}")
    return None


def _observe_progress(
    entry: DownloadEntry,
    filename: str,
    expected_size: Optional[int],
) -> None:
    """
    Daemon thread that observes .part file growth and updates entry.percentage.
    Runs while status == "downloading".
    """
    if not expected_size:
        logger.debug("No expected size; skipping progress observation")
        return

    cache_dir = MODELS_DIR / ".cache" / "huggingface" / "download"

    while entry.status == "downloading":
        # Check for .part or .incomplete files
        for variant in [f"{filename}.part", f"{filename}.incomplete"]:
            part_path = cache_dir / variant
            if part_path.exists():
                try:
                    current_size = part_path.stat().st_size
                    percentage = min(99, int((current_size / expected_size) * 100))
                    if percentage > entry.percentage:
                        entry.percentage = percentage
                        logger.debug(f"Progress: {entry.repo_id} {percentage}%")
                except Exception as e:
                    logger.debug(f"Error checking progress: {e}")
                break

        time.sleep(1)


def do_download(
    repo_id: str,
    quantization: str,
    hf_token: Optional[str],
) -> None:
    """
    Synchronous download function for use with FastAPI BackgroundTasks.
    Updates entry state as it progresses.
    """
    entry_id = sanitize_id(repo_id)
    entry = download_store.get(entry_id)

    if not entry:
        logger.error(f"Download entry not found for {repo_id}")
        return

    try:
        logger.info(f"Download started: {repo_id} ({quantization})")

        # Step 1: Find the GGUF filename
        try:
            filename = _find_gguf_filename(repo_id, quantization)
            entry.filename = filename
            logger.info(f"Target file: {filename}")
        except Exception as e:
            error_msg = f"Failed to find GGUF file: {str(e)}"
            logger.error(error_msg)
            entry.status = "failed"
            entry.error = error_msg
            return

        # Step 2: Get expected size for progress tracking
        expected_size = _get_expected_size(repo_id, filename, hf_token)
        logger.info(f"Expected size: {expected_size} bytes")

        # Step 3: Start progress observer thread
        entry.status = "downloading"
        observer_thread = threading.Thread(
            target=_observe_progress,
            args=(entry, filename, expected_size),
            daemon=True,
        )
        observer_thread.start()

        # Step 4: Download the file
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            local_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=str(MODELS_DIR),
                token=hf_token,
                repo_type="model",
            )
            logger.info(f"Downloaded to: {local_path}")
        except RepositoryNotFoundError:
            error_msg = f"Model '{repo_id}' not found on HuggingFace"
            logger.error(error_msg)
            entry.status = "failed"
            entry.error = error_msg
            return
        except GatedRepoError:
            error_msg = f"Model '{repo_id}' is gated. Please provide HF_TOKEN with access."
            logger.error(error_msg)
            entry.status = "failed"
            entry.error = error_msg
            return
        except HfHubHTTPError as e:
            error_msg = f"HuggingFace API error: {str(e)}"
            logger.error(error_msg)
            entry.status = "failed"
            entry.error = error_msg
            return
        except Exception as e:
            error_msg = f"Download failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            entry.status = "failed"
            entry.error = error_msg
            return

        # Step 5: Write verification sidecar
        try:
            verified_path = Path(local_path).with_suffix(Path(local_path).suffix + ".verified")
            metadata = {
                "repo_id": repo_id,
                "quantization": quantization,
                "filename": filename,
                "size": expected_size,
            }
            with open(verified_path, "w") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Wrote verification sidecar: {verified_path}")
        except Exception as e:
            error_msg = f"Failed to write verification sidecar: {str(e)}"
            logger.error(error_msg)
            entry.status = "failed"
            entry.error = error_msg
            return

        # Step 6: Mark as completed
        entry.status = "completed"
        entry.percentage = 100
        entry.path = local_path
        logger.info(f"Download completed: {repo_id}")

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        entry.status = "failed"
        entry.error = error_msg
