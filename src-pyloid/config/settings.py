"""Application settings and configuration."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation.
    
    Settings can be configured via environment variables with BUDDHI_ prefix.
    Example: BUDDHI_CHUNK_SIZE=16777216 for 16MB chunks.
    """

    # Models directory - will be set from Pyloid app instance
    models_dir: str = Field(
        default="",
        description="Path to models storage directory",
    )

    # Download configuration with validation
    chunk_size: int = Field(
        default=8388608,  # 8MB default
        ge=1048576,  # Min 1MB
        le=104857600,  # Max 100MB
        description="Download chunk size in bytes",
    )

    max_concurrent_downloads: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum simultaneous downloads",
    )

    download_timeout: int = Field(
        default=3600,  # 1 hour default
        ge=60,  # Min 1 minute
        le=86400,  # Max 24 hours
        description="Download timeout in seconds",
    )

    # HuggingFace configuration
    hf_token: Optional[str] = Field(
        default=None,
        min_length=20,
        description="HuggingFace API token for private repositories",
    )

    # Progress update interval
    progress_update_interval: float = Field(
        default=0.5,  # Update every 0.5 seconds
        ge=0.1,
        le=5.0,
        description="Interval between progress updates in seconds",
    )

    # Inference configuration
    default_context_size: int = Field(
        default=4096,
        ge=512,
        le=131072,
        description="Default context window size for models",
    )

    default_n_gpu_layers: int = Field(
        default=-1,  # -1 = auto-detect / use all GPU layers
        ge=-1,
        description="Default number of layers to offload to GPU (-1 for auto)",
    )

    max_loaded_models: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum number of models to keep loaded in memory",
    )

    inference_timeout: int = Field(
        default=300,  # 5 minutes
        ge=30,
        le=1800,
        description="Inference timeout in seconds",
    )

    default_max_tokens: int = Field(
        default=2048,
        ge=1,
        le=131072,
        description="Default maximum tokens to generate",
    )


    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BUDDHI_",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance.
    
    Returns:
        Settings instance
    """
    return settings


def initialize_settings(models_directory: str) -> None:
    """Initialize settings with Pyloid-specific paths.
    
    Args:
        models_directory: Path to models directory from Pyloid app
    """
    global settings
    settings.models_dir = models_directory
