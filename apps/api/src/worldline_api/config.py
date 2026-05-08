from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WORLDLINE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+pysqlite:///./worldline_p0.db"
    redis_url: str = "redis://localhost:6379/0"
    temporal_address: str = "localhost:7233"
    cors_origins: str = "http://localhost:4173,http://127.0.0.1:4173"
    auto_create_tables: bool = False
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

