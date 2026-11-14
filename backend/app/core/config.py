from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_ROOT.parent / ".env"), str(BACKEND_ROOT.parent / ".env.local")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Buddhi AI Studio Backend"
    cors_origins: list[str] = ["http://localhost:3000"]

    models_dir: Path = BACKEND_ROOT / "models" / "static"
    litert_backend: str = "cpu"
    chat_max_num_tokens: int = 16384
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

    # Agent State Machine
    agent_max_steps: int = 15
    agent_max_active_runs: int = 2
    agent_tool_output_cap: int = 4000
    agent_default_model: str = "gemma-4-e4b"

    # SearXNG & MCP
    searxng_base_url: str = "http://localhost:8080"
    searxng_timeout_s: float = 10.0
    mcp_server_name: str = "buddhi-search"
    mcp_mount_path: str = "/mcp"

    # OpenSandbox
    opensandbox_server_url: str = "http://localhost:8090"
    opensandbox_api_key: str = "changeme-opensandbox-key"
    sandbox_default_timeout_s: int = 60
    sandbox_default_memory_mb: int = 512
    sandbox_default_allow_network: bool = False
    sandbox_default_image: str = "python:3.11-slim"
    sandbox_session_inactivity_ttl_s: int = 1800
    sandbox_rlm_memory_mb: int = 256
    sandbox_rlm_idle_ttl_s: int = 300

    # RLM (Recursive Language Model)
    rlm_max_depth: int = 2
    rlm_default_snippet_tokens: int = 2048
    rlm_max_subcalls: int = 32
    rlm_subcall_concurrency: int = 2
    rlm_auto_threshold_ratio: float = 0.6

    # Crawl4AI
    crawl4ai_base_url: str = "http://localhost:11235"
    crawl4ai_api_token: str = "changeme-crawl4ai-token"
    crawl4ai_timeout_s: float = 60.0
    crawl4ai_max_payload_bytes: int = 5_242_880  # 5MB

    # RustFS Object Storage
    rustfs_endpoint_url: str = "http://localhost:9000"
    rustfs_access_key: str = "buddhi-rustfs"
    rustfs_secret_key: str = "changeme-rustfs-secret-key"
    rustfs_region: str = "us-east-1"

    # Site Crawler Tool
    site_crawler_default_bucket: str = "site-crawler"
    site_crawler_crawl_concurrency: int = 3
    site_crawler_max_pages_limit: int = 1000
    site_crawler_default_max_pages: int = 100
    site_crawler_input_token_ratio: float = 0.6
    site_crawler_max_output_tokens: int = 2048
    site_crawler_discovery_timeout_s: float = 30.0
    site_crawler_max_discovered_urls: int = 10000

    # EGM (Elephant-Goldfish Model)
    egm_enabled_default: bool = False
    egm_max_review_rounds: int = 3
    egm_goldfish_concurrency: int = 1
    egm_reviewer_timeout_s: int = 90
    egm_context_budget_tokens: int = 4096
    egm_enable_brainstorm: bool = False
    egm_default_skill_mode: str = "standard"

    # Harness2 (Recursive Agent Harnessing)
    harness_db_path: Path = BACKEND_ROOT / "data" / "harness.duckdb"
    harness_enabled_default: bool = True
    harness_auto_calibrate_uncalibrated: bool = False
    harness_auto_calibrate_on_retry: bool = True
    harness_max_calibration_rounds: int = 1
    harness_max_candidates: int = 2
    harness_probe_concurrency: int = 1
    harness_probe_max_steps: int = 6
    harness_probe_timeout_s: int = 60
    harness_max_experiences_per_workspace: int = 50
    harness_experience_token_budget: int = 2048
    harness_max_overlay_history: int = 20
    harness_calibration_retention_days: int = 30
    sandbox_max_active_sessions: int = 8

    # Trajectory Event Stream
    trajectory_queue_size: int = 2000
    trajectory_batch_size: int = 100
    trajectory_flush_interval_s: float = 0.5
    trajectory_emitter_queue_size: int = 512
    sandbox_stream_chunk_chars: int = 2048
    sandbox_stream_flush_ms: int = 100
    sandbox_max_output_bytes: int = 1_048_576


settings = Settings()
