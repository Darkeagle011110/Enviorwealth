import logging
from orchestrator.state import ConversationState
from engine.run_gates import run_gates
from engine.schemas import Tier1Intake

logger = logging.getLogger(__name__)

def rules_node(state: ConversationState) -> ConversationState:
    """
    Handles the TIER1_VERDICT state.
    Runs the deterministic engine to produce a verdict.
    """
    state["current_node"] = "TIER1_VERDICT"
    
    # 1. Convert state dict to Typed Pydantic model
    try:
        intake_dict = state.get("intake_data", {})
        intake_model = Tier1Intake(**intake_dict)
    except Exception as e:
        logger.error(f"Failed to parse intake data for rules engine: {e}")
        # fallback to empty intake if parsing completely fails
        intake_model = Tier1Intake()
        
    # 2. Run the deterministic gates
    verdict, gate_results = run_gates(intake_model)
    
    # 3. Save to state
    state["verdict"] = verdict
    # We could also save gate_results into state if needed for the UI,
    # but the verdict object contains all necessary flags.
    
    return state
