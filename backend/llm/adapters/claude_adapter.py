"""Claude (Anthropic) adapter — supports claude-3-5-sonnet, claude-3-opus, claude-3-haiku."""
import time
from typing import Dict
import anthropic
from .base_adapter import BaseLLMAdapter, LLMResponse

SUPPORTED_MODELS = [
    "claude-fable-5",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-haiku-4-5",
]


class ClaudeAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model_name: str = "claude-sonnet-5", extra_params: Dict = None):
        super().__init__(api_key, model_name, extra_params)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        params = {
            "model": self.model_name,
            "max_tokens": self.extra_params.get("max_tokens", 1500),
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }
        if "temperature" in self.extra_params:
            params["temperature"] = self.extra_params["temperature"]

        msg = await self.client.messages.create(**params)
        return LLMResponse(
            content=msg.content[0].text,
            model_used=msg.model,
            provider="claude",
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            raw=msg,
        )

    async def health_check(self) -> dict:
        start = time.monotonic()
        try:
            msg = await self.client.messages.create(
                model=self.model_name,
                max_tokens=10,
                messages=[{"role": "user", "content": "Reply OK"}],
            )
            latency = int((time.monotonic() - start) * 1000)
            return {"status": "ok", "latency_ms": latency, "model_used": msg.model, "error": None}
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            return {"status": "error", "latency_ms": latency, "model_used": self.model_name, "error": str(e)}
