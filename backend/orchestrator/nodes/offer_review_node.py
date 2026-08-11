import logging
from typing import Optional
from pydantic import BaseModel, Field
from orchestrator.state import ConversationState
from orchestrator.llm_caller import llm_caller

logger = logging.getLogger(__name__)

class OfferReviewOutput(BaseModel):
    analysis: str = Field(..., description="Plain-English analysis of the contract terms provided.")
    red_flags: list[str] = Field(default_factory=list, description="Any predatory or concerning terms detected.")
    follow_up_question: Optional[str] = Field(None, description="A question to ask to clarify the offer terms.")

SYSTEM_PROMPT = """You are a consumer protection assistant for carbon credit landowners.
The user is sharing terms of a contract or offer from a developer.
Analyze it objectively. Point out:
1. Who owns the carbon rights?
2. What happens if the trees die (reversal)?
3. What is the revenue split?
4. Are there hidden fees or exit penalties?
Flag any potentially predatory terms (e.g., locking up land for 40 years for a tiny flat fee, developer takes 100% of carbon, hidden setup costs).
Always include a disclaimer that this is not legal advice.
"""

async def offer_review_node(state: ConversationState) -> ConversationState:
    """
    Handles the OFFER_REVIEW state for consumer protection.
    """
    state["current_node"] = "OFFER_REVIEW"
    
    if not state.get("messages"):
        return state
        
    last_msg = state["messages"][-1]["content"]
    
    prompt = f"Please analyze these contract terms/questions from the user:\n\n{last_msg}"
    
    try:
        review_output = await llm_caller.call_with_schema(
            prompt=prompt,
            schema=OfferReviewOutput,
            system_prompt=SYSTEM_PROMPT
        )
        
        response = review_output.analysis
        if review_output.red_flags:
            flags = "\n".join([f"⚠️ {flag}" for flag in review_output.red_flags])
            response += f"\n\n**Things to watch out for:**\n{flags}"
            
        if review_output.follow_up_question:
            response += f"\n\n{review_output.follow_up_question}"
            
        response += "\n\n_Disclaimer: This analysis is based on standard carbon market practices and is not professional legal advice. Always consult a lawyer before signing._"
        
        state["messages"].append({"role": "assistant", "content": response})
        
    except Exception as e:
        logger.error(f"Offer review failed: {e}")
        state["messages"].append({"role": "assistant", "content": "I couldn't analyze the offer right now. Please seek independent legal advice before signing."})
        
    return state
