from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://titan:titan@localhost:5432/titan"
    temporal_target: str = "localhost:7233"
    temporal_namespace: str = "default"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "titan"
    otel_endpoint: str = "http://localhost:4317"

    model_config = SettingsConfigDict(
        env_prefix="TITAN_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
