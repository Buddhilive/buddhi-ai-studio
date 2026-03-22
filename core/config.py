from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    ollama_base_url: str = "http://localhost:11434"
    """Base URL of the Ollama server."""

    database_url: str = "sqlite:///./data/buddhi.db"
    """SQLAlchemy database URL."""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
