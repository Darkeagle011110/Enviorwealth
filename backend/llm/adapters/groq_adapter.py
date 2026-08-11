"""Groq adapter — supports llama-3.1-70b-versatile, mixtral-8x7b, gemma2-9b."""
import time
from typing import Dict
from groq import AsyncGroq
from .base_adapter import BaseLLMAdapter, LLMResponse

SUPPORTED_MODELS = [
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]


class GroqAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model_name: str = "llama-3.1-70b-versatile", extra_params: Dict = None):
        super().__init__(api_key, model_name, extra_params)
        self.client = AsyncGroq(api_key=api_key)

    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        resp = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=self.extra_params.get("max_tokens", 1500),
            temperature=self.extra_params.get("temperature", 0.3),
        )
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content,
            model_used=resp.model,
            provider="groq",
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
            raw=resp,
        )

    async def health_check(self) -> dict:
        start = time.monotonic()
        try:
            resp = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "Reply OK"}],
                max_tokens=5,
            )
            latency = int((time.monotonic() - start) * 1000)
            return {"status": "ok", "latency_ms": latency, "model_used": resp.model, "error": None}
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            return {"status": "error", "latency_ms": latency, "model_used": self.model_name, "error": str(e)}
