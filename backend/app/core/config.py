from pathlib import Path

from pydantic_settings import BaseSettings

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "Buddhi AI Studio Backend"
    cors_origins: list[str] = ["http://localhost:3000"]

    models_dir: Path = BACKEND_ROOT / "models" / "static"
    litert_backend: str = "cpu"
    chat_max_tokens_default: int = 1024
    chat_request_timeout_s: int = 120

    metrics_db_path: Path = BACKEND_ROOT / "data" / "metrics.duckdb"
    enable_trace_logging: bool = False
    trace_retention_days: int = 30
    metrics_queue_size: int = 1000
    metrics_batch_size: int = 50
    metrics_flush_interval_s: float = 2.0
    enable_prometheus_metrics: bool = False


settings = Settings()
