from typing import TypedDict, List, Optional, Any, Dict
from engine.schemas import Tier1Intake, Verdict

class ConversationState(TypedDict):
    """
    The main state object passed between all LangGraph nodes.
    """
    # General session tracking
    session_id: str
    messages: List[Dict[str, str]]  # list of {"role": "user"|"assistant", "content": "..."}
    turn_count: int
    
    # Routing and orchestration
    current_node: str               # TIER1_SCREEN, TIER1_VERDICT, etc.
    route_type: Optional[str]       # intake_answer, factual_question, edge_case, offer_review
    screening_started: bool         # True only after user explicitly requests eligibility check
    
    # Rules engine data
    intake_data: Tier1Intake
    missing_fields: List[str]       # fields still needed for the current tier
    current_question: Optional[str] # the last question asked to the user
    
    # Outcomes
    verdict: Optional[Verdict]
    lead_score: Optional[str]       # Hot, Qualified, Cold
    
    # RAG / Memory Context
    rag_citations: List[str]        # source chunk IDs for factual answers
    agentic_loop_count: int         # track iterations to bound the loop
    
    # UI State / API Response
    ui_state: Dict[str, Any]        # Structured data for frontend rendering (e.g., show memo button)
