from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver # We'll use MemorySaver for now, easy to swap to PostgresSaver later
from orchestrator.state import ConversationState

from orchestrator.nodes.greeting_node import greeting_node
from orchestrator.nodes.screen_node import screen_node
from orchestrator.nodes.rules_node import rules_node
from orchestrator.nodes.explain_node import explain_node
from orchestrator.nodes.general_qa_node import general_qa_node
from orchestrator.nodes.agentic_loop_node import agentic_loop_node
from orchestrator.nodes.offer_review_node import offer_review_node
from orchestrator.nodes.lead_node import lead_node
from orchestrator.nodes.consult_node import consult_node
from orchestrator.turn_router import route_turn

def create_orchestrator():
    """
    Assembles the LangGraph state machine for the Carbon Chatbot.
    """
    workflow = StateGraph(ConversationState)
    
    # Add Nodes
    workflow.add_node("greeting", greeting_node)
    workflow.add_node("router", route_turn)
    workflow.add_node("tier1_screen", screen_node)
    workflow.add_node("tier1_rules", rules_node)
    workflow.add_node("explain_verdict", explain_node)
    workflow.add_node("lead_scoring", lead_node)
    workflow.add_node("general_qa", general_qa_node)
    workflow.add_node("edge_case", agentic_loop_node)
    workflow.add_node("offer_review", offer_review_node)
    workflow.add_node("consult", consult_node)
    
    # Define entry point logic
    def entry_logic(state: ConversationState):
        if not state.get("messages"):
            return "greeting"
        return "router"
        
    workflow.set_conditional_entry_point(
        entry_logic,
        {
            "greeting": "greeting",
            "router": "router"
        }
    )
    
    workflow.add_edge("greeting", END)
    
    # Routing logic
    def router_logic(state: ConversationState):
        route = state.get("route_type")
        screening_started = state.get("screening_started", False)

        if route == "start_screening":
            # Explicitly flag that screening has now started
            state["screening_started"] = True
            return "tier1_screen"
        elif route in ("scepticism_handling", "green_credit_correction",
                       "out_of_scope_legal", "out_of_scope_guarantee"):
            return END
        elif route == "consult":
            return "consult"
        elif route == "factual_question":
            return "general_qa"
        elif route == "offer_review":
            return "offer_review"
        elif route == "edge_case":
            return "edge_case"
        elif route == "intake_answer" and screening_started:
            return "tier1_screen"
        else:
            # Fallback — treat as consult if screening not started
            return "consult"

    workflow.add_conditional_edges(
        "router",
        router_logic,
        {
            "general_qa": "general_qa",
            "offer_review": "offer_review",
            "edge_case": "edge_case",
            "tier1_screen": "tier1_screen",
            "consult": "consult",
            END: END
        }
    )

    
    # Screen Node Logic
    def screen_logic(state: ConversationState):
        if state.get("route_type") == "ready_for_verdict":
            return "tier1_rules"
        return END
        
    workflow.add_conditional_edges(
        "tier1_screen",
        screen_logic,
        {
            "tier1_rules": "tier1_rules",
            END: END
        }
    )
    
    # Verdict Pipeline
    workflow.add_edge("tier1_rules", "explain_verdict")
    workflow.add_edge("explain_verdict", "lead_scoring")
    workflow.add_edge("lead_scoring", END)
    
    # Other sinks
    workflow.add_edge("general_qa", END)
    workflow.add_edge("edge_case", END)
    workflow.add_edge("offer_review", END)
    workflow.add_edge("consult", END)
    
    # Memory for durable checkpointing (in-memory for local dev MVP)
    checkpointer = MemorySaver()
    
    return workflow.compile(checkpointer=checkpointer)

# Singleton instance
orchestrator_app = create_orchestrator()
