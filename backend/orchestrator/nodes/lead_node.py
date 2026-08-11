import logging
from orchestrator.state import ConversationState
from engine.schemas import VerdictCategory

logger = logging.getLogger(__name__)

def lead_node(state: ConversationState) -> ConversationState:
    """
    Evaluates the conversation state and assigns a lead score.
    Hot: PROMISING + area >= 50ha
    Qualified: POSSIBLE_NEEDS_AGGREGATION + area >= 5ha
    Cold: Anything else
    """
    verdict = state.get("verdict")
    intake = state.get("intake_data", {})
    
    if not verdict:
        state["lead_score"] = "Unknown"
        return state
        
    area = intake.get("area_ha") or 0
    category = verdict.verdict
    
    if category == VerdictCategory.promising_proceed_feasibility and area >= 50:
        state["lead_score"] = "Hot"
    elif category == VerdictCategory.possible_needs_aggregation and area >= 5:
        state["lead_score"] = "Qualified"
    else:
        state["lead_score"] = "Cold"
        
    logger.info(f"Assigned lead score: {state['lead_score']} (Area: {area}, Verdict: {category})")
    
    # In a real system, this would write to a CRM DB table here.
    
    return state
