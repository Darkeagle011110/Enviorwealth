"""
Base LLM Adapter — abstract interface all providers must implement.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any, Dict


@dataclass
class LLMResponse:
    content: str
    model_used: str
    provider: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    raw: Optional[Any] = None


class BaseLLMAdapter(ABC):
    """
    Every LLM provider adapter must implement this interface.
    The rules engine verdict is NEVER generated here — adapters only handle
    explanation, elicitation, and question generation.
    """

    def __init__(self, api_key: str, model_name: str, extra_params: Dict = None):
        self.api_key = api_key
        self.model_name = model_name
        self.extra_params = extra_params or {}

    @abstractmethod
    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        """Generate a response. Returns LLMResponse."""
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        """
        Send a minimal test prompt and return:
        { status: "ok"|"error", latency_ms: int, model_used: str, error: str|None }
        """
        ...
