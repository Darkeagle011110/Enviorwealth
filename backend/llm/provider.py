"""
LLM Provider Registry — the global singleton that holds the active LLM config.

Rules:
- The active config is loaded from the DB at startup and cached in memory.
- Admin Panel changes call `switch_provider()` which updates the cache instantly
  and persists to DB — no restart needed.
- If the primary provider fails, `get_active_llm()` automatically falls back
  to the configured fallback provider.
- All parts of the application call `get_active_llm()` — never instantiate
  adapters directly.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Optional
from sqlalchemy.orm import Session

from .adapters.base_adapter import BaseLLMAdapter, LLMResponse
from .adapters.claude_adapter import ClaudeAdapter
from .adapters.openai_adapter import OpenAIAdapter
from .adapters.groq_adapter import GroqAdapter
from .adapters.gemini_adapter import GeminiAdapter
from config.settings import settings

logger = logging.getLogger(__name__)

# Provider → Adapter class mapping
ADAPTER_MAP = {
    "claude": ClaudeAdapter,
    "openai": OpenAIAdapter,
    "groq": GroqAdapter,
    "gemini": GeminiAdapter,
}

# Available models per provider (for admin panel dropdown)
PROVIDER_MODELS = {
    "claude": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    ],
    "gemini": [
        "gemini-2.0-flash-exp",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
    ],
}


class LLMProviderRegistry:
    """
    Singleton registry for the active (and fallback) LLM adapter.
    Thread-safe for read; uses asyncio lock for writes.
    """

    def __init__(self):
        self._primary: Optional[BaseLLMAdapter] = None
        self._primary_meta: dict = {}
        self._fallback: Optional[BaseLLMAdapter] = None
        self._fallback_meta: dict = {}
        self._lock = asyncio.Lock()

    def _build_adapter(self, provider: str, model_name: str, api_key: str, extra_params: dict) -> BaseLLMAdapter:
        cls = ADAPTER_MAP.get(provider)
        if cls is None:
            raise ValueError(f"Unknown LLM provider: '{provider}'. Supported: {list(ADAPTER_MAP)}")
        return cls(api_key=api_key, model_name=model_name, extra_params=extra_params or {})

    async def initialize_from_env(self):
        """
        Bootstrap using env vars if no DB config exists yet.
        Called at app startup before the DB is checked.
        """
        provider = settings.default_llm_provider
        model = settings.default_llm_model
        key_map = {
            "claude": settings.anthropic_api_key,
            "openai": settings.openai_api_key,
            "groq": settings.groq_api_key,
            "gemini": settings.google_api_key,
        }
        api_key = key_map.get(provider, "")
        if not api_key:
            logger.warning(
                f"No API key found for default provider '{provider}'. "
                "Configure via Admin Panel before making LLM calls."
            )
            return

        async with self._lock:
            self._primary = self._build_adapter(provider, model, api_key, {})
            self._primary_meta = {"provider": provider, "model_name": model}
            logger.info(f"LLM initialized from env: {provider}/{model}")

    async def initialize_from_db(self, db: Session):
        """
        Load active + fallback configs from DB (called after DB is ready).
        Overrides the env-based bootstrap.
        """
        from models.orm_models import LLMProviderConfig
        # C3 FIX: Use Fernet encryption (not base64) for API key storage/retrieval
        from models.encryption import decrypt_data

        active = db.query(LLMProviderConfig).filter_by(is_active=True).first()
        fallback = db.query(LLMProviderConfig).filter_by(is_fallback=True).first()

        async with self._lock:
            if active:
                api_key = decrypt_data(active.api_key_enc)
                self._primary = self._build_adapter(
                    active.provider, active.model_name, api_key, active.extra_params or {}
                )
                self._primary_meta = {"provider": active.provider, "model_name": active.model_name}
                logger.info(f"Active LLM loaded from DB: {active.provider}/{active.model_name}")

            if fallback:
                api_key = decrypt_data(fallback.api_key_enc)
                self._fallback = self._build_adapter(
                    fallback.provider, fallback.model_name, api_key, fallback.extra_params or {}
                )
                self._fallback_meta = {"provider": fallback.provider, "model_name": fallback.model_name}
                logger.info(f"Fallback LLM loaded from DB: {fallback.provider}/{fallback.model_name}")

    async def switch_provider(
        self,
        provider: str,
        model_name: str,
        api_key: str,
        extra_params: dict = None,
        is_fallback: bool = False,
        db: Session = None,
    ) -> dict:
        """
        Switch the active (or fallback) LLM provider at runtime.
        Runs a health check first; only switches if the check passes.
        Persists to DB. Returns the health check result.
        """
        adapter = self._build_adapter(provider, model_name, api_key, extra_params or {})
        health = await adapter.health_check()

        if health["status"] != "ok":
            logger.error(f"LLM health check FAILED for {provider}/{model_name}: {health['error']}")
            return health  # Do NOT switch if health check fails

        async with self._lock:
            if is_fallback:
                self._fallback = adapter
                self._fallback_meta = {"provider": provider, "model_name": model_name}
                logger.info(f"Fallback LLM switched to {provider}/{model_name}")
            else:
                self._primary = adapter
                self._primary_meta = {"provider": provider, "model_name": model_name}
                logger.info(f"Active LLM switched to {provider}/{model_name}")

        # Persist to DB
        if db:
            await self._persist_to_db(db, provider, model_name, api_key, extra_params, is_fallback, health)

        return health

    async def _persist_to_db(self, db, provider, model_name, api_key, extra_params, is_fallback, health):
        from models.orm_models import LLMProviderConfig
        from datetime import datetime, timezone
        # C3 FIX: Use Fernet symmetric encryption instead of base64
        from models.encryption import encrypt_data

        # Deactivate existing config of same type
        if is_fallback:
            db.query(LLMProviderConfig).filter_by(is_fallback=True).update({"is_fallback": False})
        else:
            db.query(LLMProviderConfig).filter_by(is_active=True).update({"is_active": False})

        new_cfg = LLMProviderConfig(
            provider=provider,
            model_name=model_name,
            api_key_enc=encrypt_data(api_key),
            extra_params=extra_params or {},
            is_active=not is_fallback,
            is_fallback=is_fallback,
            last_tested_at=datetime.now(timezone.utc),
            last_test_ok=health["status"] == "ok",
            last_test_ms=health.get("latency_ms"),
        )
        db.add(new_cfg)
        db.commit()

    async def get_active_llm(self) -> BaseLLMAdapter:
        """
        Returns the active LLM adapter.
        If primary is not configured, raises RuntimeError.
        """
        if self._primary is None:
            raise RuntimeError(
                "No LLM provider configured. Please configure one via the Admin Panel."
            )
        return self._primary

    async def generate_with_fallback(self, system_prompt: str, user_message: str) -> LLMResponse:
        """
        Generate a response using the primary LLM. Automatically falls back to
        the configured fallback provider if the primary raises an exception.
        """
        try:
            llm = await self.get_active_llm()
            return await llm.generate(system_prompt, user_message)
        except Exception as primary_err:
            logger.warning(f"Primary LLM failed ({self._primary_meta}): {primary_err}")
            if self._fallback is None:
                logger.error("No fallback LLM configured. Raising primary error.")
                raise
            try:
                logger.info(f"Falling back to {self._fallback_meta}")
                return await self._fallback.generate(system_prompt, user_message)
            except Exception as fallback_err:
                logger.error(f"Fallback LLM also failed: {fallback_err}")
                raise RuntimeError(
                    f"Both primary ({self._primary_meta}) and fallback ({self._fallback_meta}) LLMs failed. "
                    f"Primary error: {primary_err}. Fallback error: {fallback_err}."
                )

    def get_status(self) -> dict:
        """Return current provider status for the Admin Panel health display."""
        return {
            "primary": self._primary_meta if self._primary else None,
            "fallback": self._fallback_meta if self._fallback else None,
            "primary_ready": self._primary is not None,
            "fallback_ready": self._fallback is not None,
        }


# ── Global singleton ──────────────────────────────────────────────────────────
llm_registry = LLMProviderRegistry()
