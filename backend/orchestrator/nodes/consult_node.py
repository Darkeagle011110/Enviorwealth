import logging
from orchestrator.state import ConversationState
from orchestrator.llm_caller import llm_caller
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class ConsultResponse(BaseModel):
    reply: str = Field(..., description="The response to the user's conversational message.")

SYSTEM_PROMPT = """You are EnviroWealth's Carbon Credit Eligibility Consultant.
The user is having a casual conversation, greeting you, or asking general non-factual questions.
Respond warmly and helpfully WITHIN the JSON 'reply' field.
If the user asks what you can do, remind them you can:
- Answer questions about carbon credits
- Check their land's eligibility
- Review contract offers
If they are ready to check their land, tell them to say "Check my eligibility".
Do not make up facts about carbon methodologies.
- You MUST NOT ask the user to provide or upload any documents, leases, or permits.

CRITICAL INSTRUCTION: You must ONLY output the raw JSON object. Do NOT output any conversational text, greetings, or thoughts outside of the JSON structure.
"""

async def consult_node(state: ConversationState) -> ConversationState:
    """
    Handles general conversational turns (greetings, chitchat) without invoking RAG.
    """
    state["current_node"] = "CONSULT"

    if not state.get("messages"):
        return state

    # Build recent context
    recent = state["messages"][-5:]
    context = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in recent])

    prompt = (
        f"Conversation history:\n{context}\n\n"
        f"Respond to the user's last message as the consultant."
    )

    try:
        output = await llm_caller.call_with_schema(
            prompt=prompt,
            schema=ConsultResponse,
            system_prompt=SYSTEM_PROMPT
        )
        state["messages"].append({"role": "assistant", "content": output.reply})
    except Exception as e:
        logger.error(f"Consult node failed: {e}")
        state["messages"].append({
            "role": "assistant",
            "content": "I'm here to help! Let me know if you want to check your land's eligibility or have questions about carbon credits."
        })

    return state
