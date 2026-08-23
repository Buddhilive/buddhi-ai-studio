from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Buddhi AI Studio Backend"
    cors_origins: list[str] = ["http://localhost:3000"]

    models_dir: Path = BACKEND_ROOT / "models" / "static"
    litert_backend: str = "cpu"
    chat_max_tokens_default: int = 1024
    chat_request_timeout_s: int = 120

    embedding_model_id: str = "embeddinggemma-300m"
    embedding_model_repo_id: str = "litert-community/embeddinggemma-300m"
    embedding_model_filename: str = "embeddinggemma-300M_seq512_mixed-precision.tflite"
    embedding_tokenizer_filename: str = "sentencepiece.model"
    embedding_cache_dir: Path = BACKEND_ROOT / "models" / "embeddings"
    embedding_device: str = "cpu"
    embedding_max_batch_size: int = 32
    embedding_seq_length: int = 512
    embedding_dim: int = 768
    embedding_num_threads: int = 4

    metrics_db_path: Path = BACKEND_ROOT / "data" / "metrics.duckdb"
    enable_trace_logging: bool = True
    trace_retention_days: int = 30
    metrics_queue_size: int = 1000
    metrics_batch_size: int = 50
    metrics_flush_interval_s: float = 2.0
    enable_prometheus_metrics: bool = False


settings = Settings()
