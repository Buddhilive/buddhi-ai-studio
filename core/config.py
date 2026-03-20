from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    hf_token: str | None = None
    """HuggingFace API token for accessing gated models."""

    hf_models_dir: str = "./data/models"
    """Directory where downloaded models are stored."""

    database_url: str = "sqlite:///./data/buddhi.db"
    """SQLAlchemy database URL."""

    inference_max_loaded_models: int = 2
    """Maximum number of GGUF models to keep loaded in memory simultaneously."""

    inference_n_ctx: int = 4096
    """Context window size (tokens) for loaded models."""

    inference_n_gpu_layers: int = 0
    """Number of layers to offload to GPU. 0 = CPU only."""

    inference_n_threads: int | None = None
    """CPU threads for inference. None = auto-detect."""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
