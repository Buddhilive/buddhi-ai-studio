"""Inference utility functions."""

import base64
import os
import re
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import aiofiles


def detect_gpu_support() -> Tuple[bool, int]:
    """Detect GPU support and number of available devices.
    
    Returns:
        Tuple of (gpu_available, device_count)
    """
    try:
        # Try to detect CUDA
        import ctypes
        try:
            # Try nvml library (NVIDIA Management Library)
            nvml = ctypes.CDLL("nvml.dll" if os.name == "nt" else "libnvidia-ml.so")
            nvml.nvmlInit()
            device_count = ctypes.c_uint()
            nvml.nvmlDeviceGetCount(ctypes.byref(device_count))
            nvml.nvmlShutdown()
            return True, device_count.value
        except (OSError, AttributeError):
            pass
        
        # Check environment variables as fallback
        cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
        if cuda_visible:
            devices = [d.strip() for d in cuda_visible.split(",") if d.strip()]
            if devices:
                return True, len(devices)
        
        return False, 0
    except Exception:
        return False, 0


def get_optimal_gpu_layers(model_size_bytes: int, available_gpu_memory: Optional[int] = None) -> int:
    """Calculate optimal number of GPU layers based on model size.
    
    Args:
        model_size_bytes: Size of the model file in bytes
        available_gpu_memory: Available GPU memory in bytes (optional)
        
    Returns:
        Recommended number of GPU layers to offload (-1 for all)
    """
    gpu_available, _ = detect_gpu_support()
    if not gpu_available:
        return 0
    
    # If no VRAM info available, try to use all layers
    if available_gpu_memory is None:
        return -1
    
    # Rough estimation: each layer uses about 2% of model size
    # Adjust based on available GPU memory
    estimated_layer_size = model_size_bytes * 0.02
    if estimated_layer_size > 0:
        max_layers = int(available_gpu_memory / estimated_layer_size)
        return min(max_layers, 100)  # Cap at 100 layers
    
    return -1  # Use all layers


def base64_to_data_uri(base64_data: str, mime_type: str = "image/png") -> str:
    """Convert base64 data to a data URI.
    
    Args:
        base64_data: Base64 encoded data (may or may not include data URI prefix)
        mime_type: MIME type for the data URI
        
    Returns:
        Complete data URI string
    """
    # Check if already a data URI
    if base64_data.startswith("data:"):
        return base64_data
    
    # Clean up the base64 data
    base64_clean = base64_data.strip()
    
    return f"data:{mime_type};base64,{base64_clean}"


def extract_base64_from_data_uri(data_uri: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract base64 data and mime type from a data URI.
    
    Args:
        data_uri: The data URI string
        
    Returns:
        Tuple of (base64_data, mime_type) or (None, None) if invalid
    """
    match = re.match(r"data:([^;]+);base64,(.+)", data_uri)
    if match:
        return match.group(2), match.group(1)
    return None, None


def is_valid_url(url: str) -> bool:
    """Check if a string is a valid HTTP/HTTPS URL.
    
    Args:
        url: The URL string to validate
        
    Returns:
        True if valid URL, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def is_data_uri(value: str) -> bool:
    """Check if a string is a data URI.
    
    Args:
        value: The string to check
        
    Returns:
        True if data URI, False otherwise
    """
    return value.startswith("data:")


async def download_image_to_base64(url: str, timeout: int = 30) -> Optional[str]:
    """Download an image from URL and convert to base64 data URI.
    
    Args:
        url: URL of the image to download
        timeout: Request timeout in seconds
        
    Returns:
        Base64 data URI string or None if download failed
    """
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Get content type
            content_type = response.headers.get("content-type", "image/png")
            if ";" in content_type:
                content_type = content_type.split(";")[0].strip()
            
            # Encode to base64
            base64_data = base64.b64encode(response.content).decode("utf-8")
            
            return f"data:{content_type};base64,{base64_data}"
    except Exception:
        return None


def estimate_memory_usage(model_path: Path) -> int:
    """Estimate memory usage for loading a model.
    
    Args:
        model_path: Path to the model file
        
    Returns:
        Estimated memory usage in bytes
    """
    if not model_path.exists():
        return 0
    
    file_size = model_path.stat().st_size
    
    # Model typically requires 1.2x - 1.5x file size in memory
    # due to context buffer, KV cache, etc.
    estimated_memory = int(file_size * 1.5)
    
    return estimated_memory


def detect_chat_format_from_filename(filename: str) -> Optional[str]:
    """Attempt to detect chat format from model filename.
    
    Args:
        filename: Model filename
        
    Returns:
        Detected chat format or None
    """
    filename_lower = filename.lower()
    
    # Common model naming patterns
    if "llama-2" in filename_lower or "llama2" in filename_lower:
        return "llama-2"
    if "llama-3" in filename_lower or "llama3" in filename_lower:
        return "llama-3"
    if "mistral" in filename_lower or "mixtral" in filename_lower:
        return "mistral-instruct"
    if "gemma" in filename_lower:
        return "gemma"
    if "phi" in filename_lower:
        return "chatml"
    if "qwen" in filename_lower:
        return "chatml"
    if "vicuna" in filename_lower:
        return "vicuna"
    if "openchat" in filename_lower:
        return "openchat"
    if "functionary" in filename_lower:
        return "functionary-v2"
    if "chatml" in filename_lower:
        return "chatml"
    
    # Default: let llama-cpp-python auto-detect from model metadata
    return None


def detect_multimodal_model(filename: str) -> Optional[str]:
    """Detect if a model is multimodal based on filename.
    
    Args:
        filename: Model filename
        
    Returns:
        Multimodal handler type or None
    """
    filename_lower = filename.lower()
    
    if "llava" in filename_lower:
        if "1.6" in filename_lower or "1-6" in filename_lower:
            return "llava-1-6"
        return "llava-1-5"
    if "moondream" in filename_lower:
        return "moondream2"
    if "minicpm" in filename_lower and "v" in filename_lower:
        return "minicpm-v-2.6"
    if "qwen" in filename_lower and "vl" in filename_lower:
        return "qwen2.5-vl"
    
    return None


def format_tool_choice(tool_choice) -> Optional[dict]:
    """Format tool choice for llama-cpp-python.
    
    Args:
        tool_choice: Tool choice from request (str or ToolChoiceObject)
        
    Returns:
        Formatted tool choice dict or None
    """
    if tool_choice is None:
        return None
    
    if isinstance(tool_choice, str):
        if tool_choice == "none":
            return None
        if tool_choice == "auto":
            return "auto"
        if tool_choice == "required":
            return "required"
    
    # ToolChoiceObject
    if hasattr(tool_choice, "function"):
        return {
            "type": "function",
            "function": {"name": tool_choice.function.name}
        }
    
    return None


def format_response_format(response_format) -> Optional[dict]:
    """Format response format for llama-cpp-python.
    
    Args:
        response_format: ResponseFormat from request
        
    Returns:
        Formatted response format dict or None
    """
    if response_format is None:
        return None
    
    result = {"type": response_format.type.value if hasattr(response_format.type, "value") else str(response_format.type)}
    
    if response_format.json_schema:
        result["schema"] = response_format.json_schema.schema_ if hasattr(response_format.json_schema, "schema_") else response_format.json_schema.get("schema", {})
    
    return result
