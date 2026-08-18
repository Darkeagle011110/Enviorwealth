from typing import TypedDict, List, Optional, Any, Dict
from engine.schemas import Tier1Intake, Verdict


class ConversationState(TypedDict):
    """
    The main state object passed between all LangGraph nodes.

    Updated for 4-agent architecture:
    - route_to: orchestrator signals which agent handles the turn
    - rag_sufficient: RAG agent signals whether web search cascade is needed
    - conversation_summary: running LLM summary of long conversations
    - web_search_results: raw results from DuckDuckGo (for audit/debug)
    """
    # ── Session tracking ──────────────────────────────────────────────────────
    session_id: str
    user_id: Optional[str]
    messages: List[Dict[str, str]]       # {"role": "user"|"assistant", "content": "..."}
    turn_count: int

    # ── Routing (set by orchestrator, read by graph edges) ────────────────────
    current_node: str                    # ORCHESTRATOR | RAG_AGENT | WEB_SEARCH_AGENT | ELIGIBILITY_AGENT
    route_to: Optional[str]             # "rag" | "eligibility" | "end"
    rag_sufficient: bool                 # False → cascade to web search

    # ── Conversation memory ───────────────────────────────────────────────────
    conversation_summary: Optional[str]  # running LLM summary for long histories

    # ── Eligibility screening ─────────────────────────────────────────────────
    screening_started: bool
    awaiting_eligibility_confirm: bool
    intake_data: Tier1Intake
    missing_fields: List[str]
    current_question: Optional[str]      # last question asked to the user

    # ── Rules engine outcomes ─────────────────────────────────────────────────
    verdict: Optional[Verdict]
    lead_score: Optional[str]            # "Hot" | "Qualified" | "Cold"

    # ── RAG / web search ──────────────────────────────────────────────────────
    rag_citations: List[str]             # chunk IDs used in RAG answer
    web_search_results: List[str]        # raw URLs from DuckDuckGo (for audit)

    # ── UI ────────────────────────────────────────────────────────────────────
    ui_state: Dict[str, Any]             # structured data for frontend rendering
