"""Utilities package."""

from .file_utils import (
    calculate_file_hash,
    cleanup_partial_download,
    get_available_space,
    get_file_size,
    get_models_directory,
    validate_gguf_file,
)
from .sse_utils import create_sse_message, sse_heartbeat
from .inference_utils import (
    base64_to_data_uri,
    detect_chat_format_from_filename,
    detect_gpu_support,
    detect_multimodal_model,
    download_image_to_base64,
    estimate_memory_usage,
    extract_base64_from_data_uri,
    format_response_format,
    format_tool_choice,
    get_optimal_gpu_layers,
    is_data_uri,
    is_valid_url,
)

__all__ = [
    "calculate_file_hash",
    "cleanup_partial_download",
    "create_sse_message",
    "get_available_space",
    "get_file_size",
    "get_models_directory",
    "sse_heartbeat",
    "validate_gguf_file",
    # Inference utils
    "base64_to_data_uri",
    "detect_chat_format_from_filename",
    "detect_gpu_support",
    "detect_multimodal_model",
    "download_image_to_base64",
    "estimate_memory_usage",
    "extract_base64_from_data_uri",
    "format_response_format",
    "format_tool_choice",
    "get_optimal_gpu_layers",
    "is_data_uri",
    "is_valid_url",
]
