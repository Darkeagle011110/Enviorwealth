"""
Turn Router — Classifies user intent to determine the next graph node.

Routes messages to one of:
  - consult              → general_qa node (greetings, open questions, general chat)
  - start_screening      → tier1_screen node (user explicitly wants eligibility check)
  - intake_answer        → tier1_screen node (ONLY when screening_started is True)
  - factual_question     → general_qa node
  - offer_review         → offer_review node
  - edge_case            → agentic_loop node
  - out_of_scope_legal   → polite refusal inline (not a node)
  - out_of_scope_guarantee → polite refusal inline

G3 compliance: out-of-scope refusal routing added per §9.4 of the brief.
"""
import logging
from orchestrator.state import ConversationState
from orchestrator.llm_schemas import TurnRoute
from orchestrator.llm_caller import llm_caller

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """You are the routing classifier for a Carbon Credit Consultant Chatbot.
Your job is to look at the user's latest message and classify it into EXACTLY one route type.

The options are STRICTLY one of:
1. "consult"               — The user is greeting, asking general questions, or having a casual conversation. 
                             Use this for: "hi", "hello", "what can you do?", "tell me about carbon credits", etc.
2. "start_screening"       — The user EXPLICITLY requests to check their land eligibility or start the screening. 
                             Use this for: "check my eligibility", "I want to see if my land qualifies", 
                             "start the assessment", "let's begin", "I have land I want to assess", etc.
3. "intake_answer"         — The user is directly answering a form question that was JUST asked about their land
                             (area, tree cover, tenure, planting status, etc.). Only use this when screening 
                             is clearly already in progress and the bot just asked a specific question.
4. "factual_question"      — The user is asking an educational question about carbon credits, standards, 
                             pricing, timelines, methodologies, Indian regulations, etc.
5. "offer_review"          — The user is asking to review a contract or offer they received from a developer.
6. "edge_case"             — A complex, multi-part, or nuanced question about their specific land situation
                             that requires deep retrieval.
7. "out_of_scope_legal"    — The user is asking for legal advice, requesting a legal guarantee, or asking 
                             for specific legal interpretation.
8. "out_of_scope_guarantee" — The user is asking for guaranteed returns, financial investment advice, 
                              or a promise of income.
9. "green_credit_correction" — The user mentions "green credits" or "GCP" (a different government scheme).
10. "scepticism_handling"  — The user is expressing doubt, calling it a scam, or asking if carbon credits are real.

CRITICAL RULES:
- Default to "consult" for any ambiguous or greeting-style message. NEVER default to "intake_answer".
- Only use "intake_answer" if: (a) the previous bot message was clearly asking a specific intake question
  AND (b) the user's reply is clearly answering that question (a number, yes/no, a land type, etc.)
- Use "start_screening" when the user shows clear intent to begin the eligibility check process.
- Prefer "factual_question" over "edge_case" for straightforward questions.
"""

# Quick keyword refusals to save LLM calls
_LEGAL_KEYWORDS = ["legal guarantee", "legally binding", "sue", "court", "lawyer", "attorney", "barrister", "advocate", "legal advice", "legal opinion"]
_GUARANTEE_KEYWORDS = ["guaranteed income", "guaranteed return", "promise me", "guarantee me", "guaranteed revenue", "100% sure", "100% certain"]
_SCREENING_KEYWORDS = ["check my eligibility", "check eligibility", "start screening", "start assessment", "assess my land", "check my land", "want to check", "want to assess", "let's begin", "let's start", "begin screening", "i have land", "my land qualifies", "does my land qualify"]

OUT_OF_SCOPE_LEGAL_REPLY = (
    "I can share general information about carbon credit frameworks, but I can't provide legal advice or legal interpretations. "
    "For anything involving contracts, land rights, or legal obligations, please consult a qualified lawyer.\n\n"
    "_This is a screening tool only — not a legal, financial, or investment service._"
)

OUT_OF_SCOPE_GUARANTEE_REPLY = (
    "I'm not able to guarantee any income or returns — and any service that does should raise a red flag. "
    "Carbon credit revenues depend on verification, methodology approval, market prices, and project performance, "
    "all of which vary. I can give you indicative ranges based on your land profile, but never a guarantee.\n\n"
    "_This is a screening assessment only — not financial or investment advice._"
)

GREEN_CREDIT_REPLY = (
    "It sounds like you're asking about the **Green Credit Programme (GCP)** run by the MoEFCC. "
    "Green Credits are a domestic Indian compliance mechanism and are distinct from voluntary carbon credits. "
    "Currently, Green Credits cannot be traded for carbon credits. I can help assess your land for *carbon* credits, "
    "but for Green Credits, you should check the official ICFRE portal."
)

SCEPTICISM_REPLY = (
    "It's smart to be cautious. The carbon market has seen its share of bad actors and unfulfilled promises. "
    "However, legitimate carbon farming is real and operates under strict international standards (like Verra or Gold Standard). "
    "My goal is to give you an objective, data-driven assessment of whether your land actually qualifies under these strict rules, "
    "so you can make an informed decision before signing any contracts."
)


async def route_turn(state: ConversationState) -> ConversationState:
    """
    Classifies the user's latest message to determine the next graph node.
    Includes fast-path keyword refusals for out-of-scope requests.
    """
    if not state.get("messages"):
        state["route_type"] = "consult"
        return state

    last_message = state["messages"][-1]["content"]
    last_lower = last_message.lower().strip()

    # Fast-path: keyword refusal for legal advice requests
    if any(kw in last_lower for kw in _LEGAL_KEYWORDS):
        state["route_type"] = "out_of_scope_legal"
        state["messages"].append({"role": "assistant", "content": OUT_OF_SCOPE_LEGAL_REPLY})
        return state

    # Fast-path: keyword refusal for guarantee requests
    if any(kw in last_lower for kw in _GUARANTEE_KEYWORDS):
        state["route_type"] = "out_of_scope_guarantee"
        state["messages"].append({"role": "assistant", "content": OUT_OF_SCOPE_GUARANTEE_REPLY})
        return state

    # Fast-path: explicit screening trigger keywords
    if any(kw in last_lower for kw in _SCREENING_KEYWORDS):
        state["route_type"] = "start_screening"
        return state

    # Fast-path heuristics for simple intake answers — ONLY when screening is already in progress
    screening_started = state.get("screening_started", False)
    if screening_started and last_lower in {"yes", "no", "owned", "leased", "i own it", "not started", "don't know", "unsure"}:
        state["route_type"] = "intake_answer"
        return state

    # Build context from recent history for better classification
    context = ""
    if len(state["messages"]) > 1:
        recent = state["messages"][-3:-1]
        context = "Recent conversation:\n" + "\n".join(
            [f"{m['role']}: {m['content'][:300]}" for m in recent]
        )

    screening_context = f"\nNote: Screening has {'already started' if screening_started else 'NOT started yet'}."

    prompt = (
        f"{context}{screening_context}\n\n"
        f"User's latest message: '{last_message}'\n\n"
        f"Classify this message into exactly one of the allowed route_type values."
    )

    try:
        route_output = await llm_caller.call_with_schema(
            prompt=prompt,
            schema=TurnRoute,
            system_prompt=ROUTER_SYSTEM_PROMPT
        )

        logger.info(f"Router → {route_output.route_type} (confidence: {route_output.confidence:.2f}), screening_started={screening_started}")
        state["route_type"] = route_output.route_type

        # Handle out-of-scope routes inline (no dedicated node needed)
        if route_output.route_type == "out_of_scope_legal":
            state["messages"].append({"role": "assistant", "content": OUT_OF_SCOPE_LEGAL_REPLY})
        elif route_output.route_type == "out_of_scope_guarantee":
            state["messages"].append({"role": "assistant", "content": OUT_OF_SCOPE_GUARANTEE_REPLY})
        elif route_output.route_type == "green_credit_correction":
            state["messages"].append({"role": "assistant", "content": GREEN_CREDIT_REPLY})
        elif route_output.route_type == "scepticism_handling":
            state["messages"].append({"role": "assistant", "content": SCEPTICISM_REPLY})

        # If the model classified as intake_answer but screening hasn't started, demote to consult
        if route_output.route_type == "intake_answer" and not screening_started:
            logger.info("Router demoted intake_answer → consult (screening not yet started)")
            state["route_type"] = "consult"

    except Exception as e:
        logger.error(f"Router failed: {e}. Defaulting to consult.")
        state["route_type"] = "consult"

    return state
