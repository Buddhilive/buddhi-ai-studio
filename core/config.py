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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
