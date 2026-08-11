"""Google Gemini adapter — supports gemini-1.5-pro, gemini-1.5-flash, gemini-2.0-flash."""
import time
from typing import Dict
import google.generativeai as genai
from .base_adapter import BaseLLMAdapter, LLMResponse

SUPPORTED_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]


class GeminiAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro", extra_params: Dict = None):
        super().__init__(api_key, model_name, extra_params)
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        # Gemini handles system prompt by prepending to user message
        combined = f"{system_prompt}\n\n---\n\n{user_message}"
        response = await self.model.generate_content_async(combined)
        return LLMResponse(
            content=response.text,
            model_used=self.model_name,
            provider="gemini",
            raw=response,
        )

    async def health_check(self) -> dict:
        start = time.monotonic()
        try:
            response = await self.model.generate_content_async("Reply OK")
            latency = int((time.monotonic() - start) * 1000)
            return {"status": "ok", "latency_ms": latency, "model_used": self.model_name, "error": None}
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            return {"status": "error", "latency_ms": latency, "model_used": self.model_name, "error": str(e)}
