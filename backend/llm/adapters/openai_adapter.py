"""OpenAI GPT adapter — supports gpt-4o, gpt-4o-mini, gpt-3.5-turbo."""
import time
from typing import Dict
from openai import AsyncOpenAI
from .base_adapter import BaseLLMAdapter, LLMResponse

SUPPORTED_MODELS = [
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-5.4",
    "gpt-5.4-pro",
    "gpt-5.4-mini",
    "gpt-5.4-nano"
]


class OpenAIAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model_name: str = "gpt-5.6-sol", extra_params: Dict = None):
        super().__init__(api_key, model_name, extra_params)
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        params = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": self.extra_params.get("max_tokens", 1500),
        }
        if "temperature" in self.extra_params:
            params["temperature"] = self.extra_params["temperature"]

        resp = await self.client.chat.completions.create(**params)
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content,
            model_used=resp.model,
            provider="openai",
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
