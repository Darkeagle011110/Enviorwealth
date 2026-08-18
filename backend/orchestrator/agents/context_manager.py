"""
context_manager.py — Conversation context summariser.

Keeps the conversation history manageable by summarising it when it
grows beyond MAX_MESSAGES or MAX_ESTIMATED_TOKENS. The summary is
stored in state["conversation_summary"] and prepended to every agent
system prompt so they have continuity without blowing the context window.
"""
import logging
from typing import List, Dict

from orchestrator.llm_caller import llm_caller
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MAX_MESSAGES = 20          # summarise when message list exceeds this
MAX_ESTIMATED_TOKENS = 3000  # rough estimate: 1 token ≈ 4 chars

# Target summary size
SUMMARY_SYSTEM_PROMPT = """You are a conversation summariser for a carbon credit eligibility chatbot.
Summarise the conversation history below into a concise, structured paragraph.
The summary MUST capture:
1. Key facts the user has stated about their land (area, tenure, location, land class, tree cover, planting status, additionality answers)
2. Any eligibility screening progress (which fields have been collected, any verdict reached)
3. Topics the user has asked about (methodologies, pricing, regulations, etc.)
4. Any red flags or special situations raised (grassland concern, FRA claim, disputed tenure, etc.)
5. Current conversation state (is screening in progress? has verdict been delivered? is the user asking follow-up questions?)

Keep the summary under 500 tokens. Write in third-person past tense. Be factual, not interpretive.
Output ONLY the summary paragraph, no headers or bullets.
"""


class SummaryOutput(BaseModel):
    summary: str = Field(..., description="Concise paragraph summarising the conversation so far.")


def _estimate_tokens(messages: List[Dict]) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return total_chars // 4


def needs_summarisation(messages: List[Dict]) -> bool:
    """Return True if the conversation is long enough to warrant summarisation."""
    if len(messages) > MAX_MESSAGES:
        return True
    if _estimate_tokens(messages) > MAX_ESTIMATED_TOKENS:
        return True
    return False


async def summarise_conversation(
    messages: List[Dict],
    existing_summary: str = "",
) -> str:
    """
    Produce a running summary of the conversation.
    If an existing summary is present, it is included as prior context
    so the new summary is cumulative, not just of recent messages.
    """
    if not messages:
        return existing_summary

    # Build the text block to summarise
    history_text = "\n".join(
        [f"{m['role'].upper()}: {m['content'][:800]}" for m in messages]
    )

    prior_context = ""
    if existing_summary:
        prior_context = f"PRIOR SUMMARY (from earlier in the conversation):\n{existing_summary}\n\n"

    prompt = (
        f"{prior_context}"
        f"RECENT MESSAGES TO SUMMARISE:\n{history_text}\n\n"
        "Produce a single updated summary covering everything above."
    )

    try:
        output = await llm_caller.call_with_schema(
            prompt=prompt,
            schema=SummaryOutput,
            system_prompt=SUMMARY_SYSTEM_PROMPT,
        )
        logger.info("Conversation summarised successfully.")
        return output.summary
    except Exception as e:
        logger.error(f"Conversation summarisation failed: {e}")
        # Fallback: return existing summary unchanged
        return existing_summary


def build_context_block(
    messages: List[Dict],
    conversation_summary: str = "",
    last_n: int = 5,
) -> str:
    """
    Build a context block to prepend to agent prompts.
    Always includes the running summary (if any) + the last N messages.
    """
    parts = []
    if conversation_summary:
        parts.append(f"[CONVERSATION SUMMARY SO FAR]\n{conversation_summary}")

    recent = messages[-last_n:] if len(messages) > last_n else messages
    if recent:
        recent_text = "\n".join(
            [f"{m['role'].capitalize()}: {m['content'][:600]}" for m in recent]
        )
        parts.append(f"[RECENT MESSAGES]\n{recent_text}")

    return "\n\n".join(parts)
