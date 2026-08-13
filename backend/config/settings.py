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
            if v.strip() == "*":
                return ["*"]
            return json.loads(v)
        return v

    # ── MongoDB ───────────────────────────────────────────────────────────────
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "envirowealth"

    # ── Qdrant (Cloud) ────────────────────────────────────────────────────────
    qdrant_url: str = "https://your-cluster.qdrant.io"
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "knowledge_chunks"
    # Embedding vector dimension — 1536 for text-embedding-3-small (MVP default)
    qdrant_vector_size: int = 1536

    # ── Admin Auth ────────────────────────────────────────────────────────────
    admin_secret_key: str = "change-me-before-production"
    jwt_secret_key: str = ""
    jwt_expire_minutes: int = 60
    admin_username: str = ""
    admin_password_hash: str = ""

    # ── LLM Defaults (overridden by DB config at runtime) ────────────────────
    default_llm_provider: str = "claude"
    default_llm_model: str = "claude-sonnet-5"

    # Bootstrap API keys (used only if DB has no config yet)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    google_api_key: str = ""

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    local_embedding_model: str = "all-MiniLM-L6-v2"

    # ── Paths ─────────────────────────────────────────────────────────────────
    uploaded_docs_path: str = "/app/uploaded_docs"
    methodologies_config_path: str = "/app/config/methodologies.yaml"


settings = Settings()
