"""
Admin Panel API — LLM Provider Management.
Endpoints for switching provider, testing config, and viewing status.
Protected by admin secret key.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from typing import Optional, Dict, List

from llm.provider import llm_registry, PROVIDER_MODELS
from models.mongodb import get_db
from config.settings import settings

router = APIRouter()

# ── GET /api/admin/llm/providers ──────────────────────────────────────────────
@router.get("/llm/providers")
async def get_providers():
    """Return all supported providers and their available models (for Admin Panel dropdowns)."""
    return {
        "providers": [
            {
                "id": provider,
                "label": {"claude": "Claude (Anthropic)", "openai": "OpenAI GPT",
                          "groq": "Groq (Llama/Mixtral)", "gemini": "Google Gemini"}[provider],
                "models": models,
            }
            for provider, models in PROVIDER_MODELS.items()
        ]
    }


# ── GET /api/admin/llm/status ─────────────────────────────────────────────────
@router.get("/llm/status")
async def get_llm_status():
    """Return current active/fallback LLM config status."""
    return llm_registry.get_status()


# ── POST /api/admin/llm/switch ────────────────────────────────────────────────
class SwitchLLMRequest(BaseModel):
    provider: str         # claude | openai | groq | gemini
    model_name: str
    api_key: str
    extra_params: Optional[Dict] = {}
    is_fallback: bool = False   # True = set as fallback, False = set as primary


@router.post("/llm/switch")
async def switch_llm(req: SwitchLLMRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Switch the active (or fallback) LLM provider.
    Runs a health check BEFORE switching.
    If health check fails, the current config is preserved — returns the failure detail.
    On success, updates both the in-memory registry AND the DB.
    """
    result = await llm_registry.switch_provider(
        provider=req.provider,
        model_name=req.model_name,
        api_key=req.api_key,
        extra_params=req.extra_params,
        is_fallback=req.is_fallback,
        db=db,
    )

    if result["status"] == "ok":
        role = "fallback" if req.is_fallback else "primary"
        return {
            "switched": True,
            "role": role,
            "provider": req.provider,
            "model_name": req.model_name,
            "health_check": result,
            "message": f"✅ {role.capitalize()} LLM switched to {req.provider}/{req.model_name} "
                       f"(latency: {result['latency_ms']}ms)",
        }
    else:
        return {
            "switched": False,
            "health_check": result,
            "message": f"❌ Health check failed for {req.provider}/{req.model_name}: {result['error']}. "
                       "Previous configuration preserved.",
        }


# ── POST /api/admin/llm/test ──────────────────────────────────────────────────
class TestLLMRequest(BaseModel):
    provider: str
    model_name: str
    api_key: str


@router.post("/llm/test")
async def test_llm(req: TestLLMRequest):
    """
    Test an LLM config WITHOUT switching the active provider.
    Use this to validate credentials before committing.
    """
    from llm.adapters.claude_adapter import ClaudeAdapter
    from llm.adapters.openai_adapter import OpenAIAdapter
    from llm.adapters.groq_adapter import GroqAdapter
    from llm.adapters.gemini_adapter import GeminiAdapter

    adapter_map = {"claude": ClaudeAdapter, "openai": OpenAIAdapter, "groq": GroqAdapter, "gemini": GeminiAdapter}
    cls = adapter_map.get(req.provider)
    if not cls:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    adapter = cls(api_key=req.api_key, model_name=req.model_name)
    return await adapter.health_check()
