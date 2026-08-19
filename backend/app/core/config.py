from pathlib import Path

from pydantic_settings import BaseSettings

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "Buddhi AI Studio Backend"
    cors_origins: list[str] = ["http://localhost:3000"]

    models_dir: Path = BACKEND_ROOT / "models" / "static"
    hf_model_repo_id: str = "litert-community/gemma-4-E2B-it-litert-lm"
    hf_model_filename: str = "gemma-4-E2B-it.litertlm"
    hf_token: str | None = None


settings = Settings()
