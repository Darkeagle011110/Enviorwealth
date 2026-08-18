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
from motor.motor_asyncio import AsyncIOMotorDatabase

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
        "claude-fable-5",
        "claude-opus-5",
        "claude-sonnet-5",
        "claude-haiku-4-5",
    ],
    "openai": [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.4",
        "gpt-5.4-pro",
        "gpt-5.4-mini",
        "gpt-5.4-nano"
    ],
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

    async def initialize_from_db(self, db: AsyncIOMotorDatabase):
        """
        Load active + fallback configs from DB (called after DB is ready).
        Overrides the env-based bootstrap.
        """
        # C3 FIX: Use Fernet encryption (not base64) for API key storage/retrieval
        from models.encryption import decrypt_data

        active = await db.llm_provider_configs.find_one({"is_active": True})
        fallback = await db.llm_provider_configs.find_one({"is_fallback": True})

        async with self._lock:
            if active:
                try:
                    api_key = decrypt_data(active.get("api_key_enc", ""))
                    self._primary = self._build_adapter(
                        active.get("provider"), active.get("model_name"), api_key, active.get("extra_params", {})
                    )
                    self._primary_meta = {"provider": active.get("provider"), "model_name": active.get("model_name")}
                    logger.info(f"Active LLM loaded from DB: {active.get('provider')}/{active.get('model_name')}")
                except Exception as e:
                    logger.error(
                        f"Failed to initialise primary LLM adapter from DB config "
                        f"({active.get('provider')}/{active.get('model_name')}): {e}. "
                        "Server will fall back to env-var configuration.",
                        exc_info=True,
                    )

            if fallback:
                try:
                    api_key = decrypt_data(fallback.get("api_key_enc", ""))
                    self._fallback = self._build_adapter(
                        fallback.get("provider"), fallback.get("model_name"), api_key, fallback.get("extra_params", {})
                    )
                    self._fallback_meta = {"provider": fallback.get("provider"), "model_name": fallback.get("model_name")}
                    logger.info(f"Fallback LLM loaded from DB: {fallback.get('provider')}/{fallback.get('model_name')}")
                except Exception as e:
                    logger.error(
                        f"Failed to initialise fallback LLM adapter from DB config "
                        f"({fallback.get('provider')}/{fallback.get('model_name')}): {e}.",
                        exc_info=True,
                    )

    async def switch_provider(
        self,
        provider: str,
        model_name: str,
        api_key: str,
        extra_params: dict = None,
        is_fallback: bool = False,
        db: AsyncIOMotorDatabase = None,
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
        if db is not None:
            await self._persist_to_db(db, provider, model_name, api_key, extra_params, is_fallback, health)

        return health

    async def _persist_to_db(self, db: AsyncIOMotorDatabase, provider, model_name, api_key, extra_params, is_fallback, health):
        from datetime import datetime, timezone
        from models.schemas import LLMProviderConfigDoc
        # C3 FIX: Use Fernet symmetric encryption instead of base64
        from models.encryption import encrypt_data

        # Deactivate existing config of same type
        if is_fallback:
            await db.llm_provider_configs.update_many({"is_fallback": True}, {"$set": {"is_fallback": False}})
        else:
            await db.llm_provider_configs.update_many({"is_active": True}, {"$set": {"is_active": False}})

        new_cfg = LLMProviderConfigDoc(
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
        await db.llm_provider_configs.insert_one(new_cfg.model_dump())

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
