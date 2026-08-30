from __future__ import annotations

import logging
import os
import shutil
import subprocess

import psutil
from litert_lm import Backend

from app.schemas.settings import SupportedBackend, SystemResourceRecommendation

logger = logging.getLogger(__name__)

# Constants for token capacity estimation
MODEL_WEIGHTS_BYTES = 3_700_000_000  # ~3.7 GB for Gemma 4 E4B int4
OS_RESERVE_BYTES = 1_800_000_000      # ~1.8 GB system reserve
BYTES_PER_TOKEN = 150_000             # ~150 KB KV cache per token (FP16 GQA)


def _detect_gpu() -> tuple[str | None, int | None, int | None]:
    """Detects NVIDIA GPU details if nvidia-smi is available."""
    smi_path = shutil.which("nvidia-smi")
    if not smi_path:
        return None, None, None
    try:
        out = subprocess.check_output(
            [
                smi_path,
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=2.0,
        ).strip()
        lines = out.splitlines()
        if not lines:
            return None, None, None
        parts = [p.strip() for p in lines[0].split(",")]
        gpu_name = parts[0]
        total_mb = int(parts[1])
        free_mb = int(parts[2])
        return gpu_name, total_mb * 1024 * 1024, free_mb * 1024 * 1024
    except Exception as exc:
        logger.debug("Failed to query GPU via nvidia-smi: %s", exc)
        return None, None, None


def _check_npu_supported() -> tuple[bool, str | None]:
    """Checks if NPU backend can be instantiated via LiteRT."""
    try:
        Backend.NPU()
        return True, None
    except Exception as exc:
        return False, str(exc)


def _check_gpu_supported() -> tuple[bool, str | None]:
    """Checks if GPU backend can be instantiated via LiteRT."""
    try:
        Backend.GPU()
        return True, None
    except Exception as exc:
        return False, str(exc)


def get_system_resource_recommendation() -> SystemResourceRecommendation:
    """Analyzes host memory, CPU, and accelerators to compute recommended tokens and backend."""
    mem = psutil.virtual_memory()
    total_ram = mem.total
    avail_ram = mem.available
    cpu_count = os.cpu_count() or 1

    gpu_name, gpu_total, gpu_free = _detect_gpu()
    gpu_supported_by_lib, gpu_lib_err = _check_gpu_supported()
    npu_supported, npu_reason = _check_npu_supported()

    # Determine backend recommendations
    gpu_viable = bool(gpu_supported_by_lib and gpu_name and (gpu_total or 0) >= 4 * 1024**3)
    recommended_backend: str = "gpu" if gpu_viable else "cpu"

    supported_backends: list[SupportedBackend] = [
        SupportedBackend(
            id="cpu",
            name="CPU",
            supported=True,
            recommended=(recommended_backend == "cpu"),
        )
    ]

    if gpu_viable:
        supported_backends.append(
            SupportedBackend(
                id="gpu",
                name=f"GPU ({gpu_name})",
                supported=True,
                recommended=True,
            )
        )
    elif gpu_supported_by_lib:
        supported_backends.append(
            SupportedBackend(
                id="gpu",
                name="GPU",
                supported=True,
                recommended=False,
                reason="No dedicated GPU with >= 4GB VRAM detected",
            )
        )
    else:
        supported_backends.append(
            SupportedBackend(
                id="gpu",
                name="GPU",
                supported=False,
                recommended=False,
                reason=gpu_lib_err or "GPU delegate unavailable",
            )
        )

    supported_backends.append(
        SupportedBackend(
            id="npu",
            name="NPU",
            supported=npu_supported,
            recommended=False,
            reason=None if npu_supported else (npu_reason or "NPU delegate unavailable"),
        )
    )

    # Token capacity estimation based on available host RAM
    usable_kv_ram = max(0, avail_ram - (MODEL_WEIGHTS_BYTES + OS_RESERVE_BYTES))
    raw_tokens = usable_kv_ram // BYTES_PER_TOKEN

    if raw_tokens >= 32768 and total_ram >= 24 * 1024**3:
        recommended_max_num_tokens = 16384
        max_viable_tokens = 32768
    elif raw_tokens >= 16384 or avail_ram >= 8 * 1024**3:
        recommended_max_num_tokens = 16384
        max_viable_tokens = 16384
    elif raw_tokens >= 8192 or avail_ram >= 6 * 1024**3:
        recommended_max_num_tokens = 8192
        max_viable_tokens = 8192
    elif raw_tokens >= 4096:
        recommended_max_num_tokens = 4096
        max_viable_tokens = 4096
    else:
        recommended_max_num_tokens = 2048
        max_viable_tokens = 2048

    avail_gb = avail_ram / (1024**3)
    total_gb = total_ram / (1024**3)

    gpu_snippet = f" and {gpu_name} ({gpu_total / (1024**3):.1f} GB VRAM)" if gpu_name and gpu_total else ""
    reasoning = (
        f"Detected {total_gb:.1f} GB total RAM ({avail_gb:.1f} GB available){gpu_snippet}. "
        f"With ~3.7 GB for model weights and 1.8 GB system reserve, "
        f"your system safely supports {recommended_max_num_tokens:,} tokens "
        f"(up to {max_viable_tokens:,}). "
        f"Recommended backend: {recommended_backend.upper()}."
    )

    return SystemResourceRecommendation(
        total_memory_bytes=total_ram,
        available_memory_bytes=avail_ram,
        cpu_count=cpu_count,
        gpu_name=gpu_name,
        gpu_total_memory_bytes=gpu_total,
        gpu_free_memory_bytes=gpu_free,
        supported_backends=supported_backends,
        recommended_backend=recommended_backend,  # type: ignore[arg-type]
        recommended_max_num_tokens=recommended_max_num_tokens,
        max_viable_tokens=max_viable_tokens,
        model_assumed="Gemma 4 E4B",
        reasoning=reasoning,
    )
