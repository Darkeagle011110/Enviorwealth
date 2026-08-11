import json
import logging
from typing import Type, TypeVar, Optional, Any, Dict, List
from pydantic import BaseModel, ValidationError

from llm.provider import llm_registry

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class LLMCallerError(Exception):
    pass

class LLMCaller:
    """
    Wrapper around the LLM Registry to enforce Structured Outputs,
    handle retries, and validate Pydantic schemas on the output.
    All callers must go through this class — never instantiate adapters directly.
    """

    @staticmethod
    async def call_with_schema(
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        max_retries: int = 2
    ) -> T:
        """
        Calls the active LLM provider and enforces a Pydantic schema for the output.
        Falls back automatically if the primary provider fails.

        C1 FIX: Was previously calling non-existent `llm_registry.generate()`.
        Now correctly uses `llm_registry.generate_with_fallback()`.
        """
        if system_prompt is None:
            system_prompt = "You are a helpful carbon credit consultant AI."

        enriched_system = (
            system_prompt
            + f"\n\nYou MUST return your answer in valid JSON matching the following schema:\n"
            f"{schema.schema_json()}\n"
            f"Do not include markdown code fences or any text before or after the JSON."
        )

        last_error = None
        current_prompt = prompt

        for attempt in range(max_retries + 1):
            try:
                # C1 FIX: llm_registry.generate() does NOT exist.
                # The registry exposes generate_with_fallback(system_prompt, user_message).
                resp = await llm_registry.generate_with_fallback(
                    system_prompt=enriched_system,
                    user_message=current_prompt,
                )
                raw_response = resp.content

                # Strip potential markdown fences and chatty pre-text
                cleaned = raw_response.strip()
                
                # First try to find a JSON object block
                if "```json" in cleaned:
                    cleaned = cleaned.split("```json")[1].split("```")[0].strip()
                elif "```" in cleaned:
                    cleaned = cleaned.split("```")[1].split("```")[0].strip()
                else:
                    # If no fences, try to extract between first { and last }
                    start_idx = cleaned.find('{')
                    end_idx = cleaned.rfind('}')
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        cleaned = cleaned[start_idx:end_idx+1].strip()

                # Parse and validate against schema
                parsed_json = json.loads(cleaned)
                validated_model = schema(**parsed_json)
                return validated_model

            except json.JSONDecodeError as e:
                last_error = f"JSON decode error on attempt {attempt + 1}: {e}"
                logger.warning(last_error)
            except ValidationError as e:
                last_error = f"Schema validation error on attempt {attempt + 1}: {e}"
                logger.warning(last_error)
            except Exception as e:
                last_error = str(e)
                logger.error(f"LLM generation failed on attempt {attempt + 1}: {e}")

            # Feedback loop — tell the model what went wrong
            current_prompt = (
                prompt
                + f"\n\n[SYSTEM VALIDATION ERROR — Attempt {attempt + 1}]: {last_error}. "
                "Respond ONLY with valid JSON matching the schema. No explanations."
            )

        raise LLMCallerError(
            f"Failed to produce valid structured output after {max_retries + 1} attempts. "
            f"Last error: {last_error}"
        )


llm_caller = LLMCaller()
