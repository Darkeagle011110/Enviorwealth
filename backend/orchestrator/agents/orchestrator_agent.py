"""
orchestrator_agent.py — The master routing agent with an LLM brain.

The Orchestrator is the "thinking" centre of the system. It uses its LLM to:
  1. Understand the user's intent from context + current query
  2. Answer simple questions ITSELF (greetings, "what can you do?", out-of-domain)
  3. Route to the correct sub-agent when specialised knowledge is needed

NO regex. NO keyword lists. The LLM reads the conversation and decides.

Routes to downstream agents:
  - "rag"         → RAG Agent (domain knowledge Q&A about carbon credits)
  - "eligibility" → Eligibility Agent (user wants to check eligibility of something)
  - "inline"      → Orchestrator answers directly (greetings, simple questions, out-of-domain)
"""
import logging
from orchestrator.state import ConversationState
from orchestrator.llm_caller import llm_caller
from orchestrator.llm_schemas import OrchestratorDecision
from orchestrator.agents.context_manager import (
    needs_summarisation,
    summarise_conversation,
    build_context_block,
)

logger = logging.getLogger(__name__)

# ─── System prompt: the Orchestrator's brain ──────────────────────────────────

ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator of EnviroWealth's Carbon Credit Eligibility Chatbot.

You have 3 sub-agents you can delegate to, OR you can answer the user directly.

## Your Sub-Agents

1. **RAG Agent** ("rag") — Has access to a knowledge base about carbon credits, Indian carbon
   regulations (CCTS, VM0047, Gold Standard, Plan Vivo), methodologies, economics, timelines,
   project lifecycle, contract review, and carbon market information.
   Route here when the user asks a FACTUAL or INFORMATIONAL question about carbon credits or
   related topics that needs specific data from the knowledge base.

2. **Eligibility Agent** ("eligibility") — Handles ANY eligibility-related query.
   This agent is smart — it will determine internally whether the eligibility question is about
   carbon credits (in which case it pops up a screening form and runs the 10-gate rules engine)
   or about something else (in which case it searches the web for an answer).
   Route here whenever the user's intent involves checking whether they/their land/their project
   qualifies or is eligible for something.

3. **Web Search Agent** — You do NOT route to this directly. The RAG agent cascades to it
   automatically if the knowledge base has no answer.

## When YOU Answer Directly ("inline")

Answer the user yourself (without routing to any sub-agent) for:
- **Greetings & introductions**: "Hi", "Hello", "What can you do?", "Who are you?"
- **Simple conversational replies**: "Thank you", "OK", "Got it"
- **Out-of-domain queries**: Questions completely unrelated to carbon credits, eligibility, or
  environmental markets (e.g., "What's the weather?", "Help me cook pasta")
  → Politely explain you're a carbon credit eligibility assistant and offer to help with that instead.
- **Hard refusals**: Legal advice requests, guaranteed return promises
  → Politely refuse and explain why.

## Decision Rules

- If an eligibility offer is pending (awaiting_eligibility_confirm=True) and the user says "Yes", "Sure", "Check it", or any affirmative → route to "eligibility".
- If the user mentions checking eligibility, qualifying, registering, assessing their land/project/
  facility, or anything that suggests they want to know if they or their project can get something
  → route to "eligibility"
- If the user asks an informational question about carbon credits, methodologies, regulations, 
  pricing, timelines, species, costs, etc. → route to "rag"
- If the user is just chatting, greeting, or asking something unrelated → answer "inline"
- When in doubt between "rag" and "eligibility", think about whether the user wants INFORMATION
  or wants an ASSESSMENT. Information = rag. Assessment = eligibility.

## Output Format

You must output:
- route_to: "rag", "eligibility", or "inline"
- reply: Your direct answer to the user (ONLY used when route_to is "inline". Leave empty otherwise.)
- reasoning: Brief internal reasoning for your routing decision.
"""


async def orchestrator_agent(state: ConversationState) -> ConversationState:
    """
    Master routing agent. Uses its LLM brain to understand the user's intent
    and either answer directly or route to the appropriate sub-agent.
    """
    state["current_node"] = "ORCHESTRATOR"
    state.setdefault("conversation_summary", "")
    state.setdefault("rag_sufficient", True)
    state.setdefault("screening_started", False)

    messages = state.get("messages", [])

    # ── Conversation summarisation (keep history manageable) ──────────────────
    if needs_summarisation(messages):
        to_summarise = messages[:-5] if len(messages) > 5 else messages
        state["conversation_summary"] = await summarise_conversation(
            to_summarise,
            existing_summary=state.get("conversation_summary", ""),
        )
        logger.info("Conversation summarised (history was long).")

    # ── Get the latest user message ───────────────────────────────────────────
    if not messages:
        state["route_to"] = "end"
        return state

    last_user_msg = next(
        (m for m in reversed(messages) if m.get("role") == "user"), None
    )
    if not last_user_msg:
        state["route_to"] = "end"
        return state

    user_text = last_user_msg.get("content", "")

    # ── Build context for the LLM ─────────────────────────────────────────────
    context_block = build_context_block(
        messages,
        conversation_summary=state.get("conversation_summary", ""),
        last_n=5,
    )

    # Add screening state context so the LLM knows if eligibility is in progress
    screening_context = ""
    if state.get("screening_started"):
        screening_context += (
            "\n[SYSTEM NOTE: An eligibility screening is currently in progress. "
            "If the user's message looks like an answer to a screening question "
            "(e.g., land area, tenure type, tree cover, etc.), route to 'eligibility'.]"
        )
    if state.get("awaiting_eligibility_confirm"):
        screening_context += (
            "\n[SYSTEM NOTE: awaiting_eligibility_confirm=True. The user was just offered "
            "an eligibility check. If their message is affirmative (Yes, Sure, OK), route to 'eligibility'.]"
        )

    prompt = (
        f"{context_block}"
        f"{screening_context}\n\n"
        f"User's latest message: \"{user_text}\"\n\n"
        "Decide: should you answer this yourself (inline), or route to a sub-agent?"
    )

    try:
        decision = await llm_caller.call_with_schema(
            prompt=prompt,
            schema=OrchestratorDecision,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        )

        route = decision.route_to.lower().strip()
        logger.info(f"Orchestrator LLM → {route} (reason: {decision.reasoning[:80]})")

        if route == "inline":
            # Orchestrator answers directly
            state["messages"].append({
                "role": "assistant",
                "content": decision.reply,
            })
            state["route_to"] = "end"
        elif route in ("rag", "eligibility"):
            state["route_to"] = route
        else:
            # Unknown route — default to RAG as safest option
            logger.warning(f"Orchestrator returned unknown route '{route}', defaulting to rag")
            state["route_to"] = "rag"

    except Exception as e:
        logger.error(f"Orchestrator LLM failed: {e}")
        # Fallback: try to answer with a generic helpful message
        state["messages"].append({
            "role": "assistant",
            "content": (
                "I'm having a brief technical issue, but I'm here to help! "
                "I can assist you with:\n"
                "- **Questions** about carbon credits, methodologies, and Indian regulations\n"
                "- **Checking eligibility** of your land or project for carbon credits\n"
                "- **Reviewing** contract offers from developers\n\n"
                "Please try your question again, or say **\"Check my eligibility\"** to start."
            ),
        })
        state["route_to"] = "end"

    return state
