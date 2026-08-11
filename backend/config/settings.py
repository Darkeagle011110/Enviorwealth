"""
Application settings — loaded from environment variables / .env file.
All LLM credentials are managed at RUNTIME via the Admin Panel DB record,
not from this file. This file provides startup defaults and infrastructure config.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Literal, List
import json

import os
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_path,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+psycopg2://carbon:carbonpass@localhost:5432/carbondb"
    # Async URL for async SQLAlchemy usage
    @property
    def async_database_url(self) -> str:
        return self.database_url.replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Admin Auth ────────────────────────────────────────────────────────────
    admin_secret_key: str = "change-me-before-production"
    jwt_secret_key: str = ""
    jwt_expire_minutes: int = 60
    admin_username: str = ""
    admin_password_hash: str = ""

    # ── LLM Defaults (overridden by DB config at runtime) ────────────────────
    default_llm_provider: str = "claude"
    default_llm_model: str = "claude-3-5-sonnet-20241022"

    # Bootstrap API keys (used only if DB has no config yet)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    google_api_key: str = ""

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-large"
    local_embedding_model: str = "all-MiniLM-L6-v2"

    # ── Paths ─────────────────────────────────────────────────────────────────
    uploaded_docs_path: str = "/app/uploaded_docs"
    methodologies_config_path: str = "/app/config/methodologies.yaml"


settings = Settings()
