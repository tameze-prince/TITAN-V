from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://titan:titan@localhost:5432/titan"
    temporal_target: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "titan-core"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "titan"
    otel_endpoint: str = "http://localhost:4317"
    model_provider: str = "local"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5"
    openai_base_url: str | None = None
    agent_execution_timeout_seconds: int = 120
    general_agent_max_concurrency: int = 4
    engineering_agent_max_concurrency: int = 2
    sandbox_image: str = "python:3.13-slim"
    sandbox_network: str = "none"
    sandbox_memory: str = "512m"
    sandbox_cpus: str = "1.0"
    sandbox_pids_limit: int = 128
    sandbox_timeout_seconds: int = 60
    workspace_root: str = ".titan/workspaces"
    model_max_input_tokens: int = 64_000
    model_max_output_tokens: int = 16_000
    model_max_cost: float = 0.0
    orchestration_max_cost: float = 0.0
    openai_input_cost_per_1k: float = 0.0
    openai_output_cost_per_1k: float = 0.0

    model_config = SettingsConfigDict(
        env_prefix="TITAN_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
