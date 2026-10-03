"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application settings. Values sourced from .env or environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Gemini AI ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_tokens: int = 8192
    gemini_timeout_seconds: int = 30

    # --- Database ---
    duckdb_path: str = "./ps3_analysis.db"

    # --- Ingestion ---
    data_root: str = "../data/synthetic"
    max_file_size_bytes: int = 104_857_600  # 100 MB

    # --- Correlation ---
    temporal_window_seconds: float = 10.0

    # --- Application ---
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    log_level: str = "INFO"
    debug: bool = False

    @field_validator("gemini_api_key")
    @classmethod
    def _warn_missing_key(cls, v: str) -> str:
        # We don't raise here — AI features will be disabled gracefully
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def duckdb_path_resolved(self) -> Path:
        p = Path(self.duckdb_path)
        if not p.is_absolute():
            # Resolve relative to backend directory
            p = Path(__file__).parent.parent / p
        return p

    @property
    def data_root_resolved(self) -> Path:
        p = Path(self.data_root)
        if not p.is_absolute():
            p = Path(__file__).parent.parent.parent / p
        return p.resolve()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
