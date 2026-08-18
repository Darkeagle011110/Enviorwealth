"""
graph.py — LangGraph state machine for the EnviroWealth Carbon Chatbot.

4-agent architecture:
  ┌─────────────────────────────────────────────────────────────┐
  │                   ORCHESTRATOR AGENT                        │
  │  (3-tier routing: keyword → heuristic → LLM fallback)      │
  │  Handles: greetings, refusals, green credit correction      │
  └──────┬─────────────────────────┬──────────────────┬────────┘
         │ route_to="rag"          │ route_to=         │ route_to="end"
         ▼                         │ "eligibility"     ▼
  ┌──────────────────┐             │            ┌─────┐
  │   RAG AGENT      │             ▼            │ END │
  │  (Qdrant KB +    │  ┌──────────────────────┐│     │
  │   agentic loop)  │  │  ELIGIBILITY AGENT   ││     │
  └──────┬───────────┘  │  (form + gates +     ││     │
         │              │   verdict + lead)     ││     │
         │ rag_         └──────────────────────┘│     │
         │ sufficient=                           │     │
         │ False                                 │     │
         ▼                                       │     │
  ┌──────────────────┐                           │     │
  │ WEB SEARCH AGENT │                           │     │
  │  (DuckDuckGo)    │                           │     │
  └──────────────────┘                           └─────┘

Thread ID: Uses session_id (not session_id__turn_N) so MemorySaver
correctly tracks state across turns.
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import logging

logger = logging.getLogger(__name__)

from orchestrator.state import ConversationState
from orchestrator.agents.orchestrator_agent import orchestrator_agent
from orchestrator.agents.rag_agent import rag_agent
from orchestrator.agents.web_search_agent import web_search_agent
from orchestrator.agents.eligibility_agent import eligibility_agent


def create_orchestrator():
    """
    Assembles the 4-agent LangGraph state machine.
    """
    workflow = StateGraph(ConversationState)

    # ── Register the 4 agents as nodes ───────────────────────────────────────
    workflow.add_node("orchestrator", orchestrator_agent)
    workflow.add_node("rag", rag_agent)
    workflow.add_node("web_search", web_search_agent)
    workflow.add_node("eligibility", eligibility_agent)

    # ── Entry point: always start at the orchestrator ──────────────────────────
    workflow.set_entry_point("orchestrator")

    # ── Orchestrator → downstream routing ─────────────────────────────────────
    def orchestrator_to_agent(state: ConversationState) -> str:
        """Route from orchestrator to the appropriate agent."""
        route = state.get("route_to", "end")
        if route == "rag":
            logger.info(f"[GRAPH] Edge: Orchestrator ──────> RAG Agent")
            return "rag"
        elif route == "eligibility":
            logger.info(f"[GRAPH] Edge: Orchestrator ──────> Eligibility Agent")
            return "eligibility"
        else:
            logger.info(f"[GRAPH] Edge: Orchestrator ──────> END (Inline reply)")
            return END  # "end" — orchestrator replied inline

    workflow.add_conditional_edges(
        "orchestrator",
        orchestrator_to_agent,
        {
            "rag": "rag",
            "eligibility": "eligibility",
            END: END,
        },
    )

    # ── RAG → web search cascade ───────────────────────────────────────────────
    def rag_to_next(state: ConversationState) -> str:
        """If RAG was insufficient, cascade to web search. Otherwise END."""
        if not state.get("rag_sufficient", True):
            logger.info(f"[GRAPH] Edge: RAG Agent ──────> Web Search Agent (Fallback)")
            return "web_search"
        logger.info(f"[GRAPH] Edge: RAG Agent ──────> END")
        return END

    workflow.add_conditional_edges(
        "rag",
        rag_to_next,
        {
            "web_search": "web_search",
            END: END,
        },
    )

    # ── All other agents → END ────────────────────────────────────────────────
    workflow.add_edge("web_search", END)
    workflow.add_edge("eligibility", END)

    # ── Persistent checkpointing ───────────────────────────────────────────────
    # MemorySaver for local dev — swap for PostgresSaver in production
    checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)


# ── Singleton ──────────────────────────────────────────────────────────────────
orchestrator_app = create_orchestrator()
