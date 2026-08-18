"""
eligibility_agent.py — The eligibility pipeline agent with its own LLM brain.

Triggered by the Orchestrator when the user's intent involves checking eligibility.

This agent is SMART — it uses a single LLM decision call to determine the next action:
- show_form: Pop up the eligibility form modal immediately
- search_and_offer: Search DuckDuckGo, answer, and offer to check eligibility
- accept_confirm: User accepted the offer, show form modal
- run_verdict: Form submitted, parse and run gates engine
- passthrough: Let orchestrator handle
"""
import json
import logging
from typing import Optional
from pydantic import BaseModel, Field

from orchestrator.state import ConversationState
from orchestrator.llm_caller import llm_caller
from orchestrator.llm_schemas import ExplainOutput
from orchestrator.agents.context_manager import build_context_block
from orchestrator.agents.web_search_agent import (
    _duckduckgo_search,
    _build_search_context,
    WebSearchAnswer,
    WEB_ANSWER_SYSTEM,
)
from engine.schemas import Tier1Intake, GateStatus, VerdictCategory
from engine.gates import GATES
from engine.verdict import assemble_verdict
from geospatial.geo_service import geo_service

logger = logging.getLogger(__name__)


class EligibilityAgentDecision(BaseModel):
    next_action: str = Field(
        ...,
        description='One of: "show_form", "search_and_offer", "accept_confirm", "run_verdict", "passthrough"'
    )
    search_query: Optional[str] = Field(
        None,
        description='A specific DuckDuckGo search query including India context, only if next_action == "search_and_offer"'
    )
    reply: Optional[str] = Field(
        None,
        description='Optional direct reply to prepend or send to the user'
    )
    reasoning: str = Field(
        ...,
        description='Brief internal reasoning for this decision'
    )


AGENT_SYSTEM_PROMPT = """You are the decision brain of EnviroWealth's Eligibility Agent.

You have access to these TOOLS (actions you can invoke):

1. show_form
   Call this when the user clearly wants to check THEIR OWN eligibility right now.
   Signs: "check my eligibility", "is my land eligible?", "I want to check",
          user said YES to an earlier offer to check eligibility.
   Do NOT search first. Pop the form immediately.

2. search_and_offer
   Call this when the user asked an INFORMATIONAL question about eligibility
   (not personal — they want to understand the topic, not screen their specific land).
   Signs: "which lands are eligible?", "what are the criteria for carbon credits?",
          "how does eligibility work?", "tell me about eligible land types".
   Perform a DuckDuckGo web search, give a useful answer, then append a polite
   offer: "Would you like to check your own land's eligibility? Just say Yes."

3. accept_confirm
   Call this when: awaiting_eligibility_confirm is True AND the user said yes/sure/ok/proceed.
   This pops the form modal.

4. run_verdict
   Call this when: the last user message contains a JSON blob with key "eligibility_form".
   This means the user submitted the form. Parse all fields. Run the rules engine. Deliver verdict.
   NEVER ask follow-up field questions after this.

5. passthrough
   Call this if you are unsure, or the message doesn't fit any of the above.
   The orchestrator will handle it.

IMPORTANT: When run_verdict is triggered, you must NOT ask the user any more questions
about their land. All required data comes from the form submission. Evaluate immediately.
"""

EXPLAIN_SYSTEM = """You are the explanation layer of the EnviroWealth Carbon Credit Consultant.
Your ONLY job is to explain the verdict the deterministic rules engine has already produced.
You do NOT decide eligibility — the verdict is fixed.

Instructions:
- Explain WHY the verdict is what it is, in plain, empathetic English.
- If it's a structural knockout (e.g., recorded forest land, disputed tenure), be direct but polite.
  Point to alternatives (forest department routes, Green Credit Programme, non-credit incentives).
- If it's promising, be honest about the timeline (3–7 years to first credit) and buffer witholding.
- Do NOT promise guaranteed returns.
- Do NOT ask the user to upload documents or permits.
- Include the financial indicative range ONLY if the verdict is promising or possible.
"""

def _score_lead(verdict, intake: dict) -> str:
    area = intake.get("area_ha") or 0
    category = getattr(verdict, "verdict", None)
    if category == VerdictCategory.promising_proceed_feasibility and area >= 50:
        return "Hot"
    elif category == VerdictCategory.possible_needs_aggregation and area >= 5:
        return "Qualified"
    return "Cold"


# ─── Canonical field alias map ────────────────────────────────────────────────
# Maps common admin-panel field_id names → Tier1Intake field names.
# Extend this when new form fields are added.
_FIELD_ALIASES: dict[str, str] = {
    # Area
    "area": "area_ha",
    "land_area": "area_ha",
    "area_acres": "area_ha",   # NOTE: caller should convert acres → ha before this
    "land_size": "area_ha",
    "size_ha": "area_ha",
    "size": "area_ha",
    # Tenure
    "tenure": "tenure_type",
    "ownership": "tenure_type",
    "land_ownership": "tenure_type",
    "ownership_type": "tenure_type",
    # Legal class
    "legal_class": "land_legal_class",
    "land_class": "land_legal_class",
    "land_type": "land_legal_class",
    "classification": "land_legal_class",
    "land_classification": "land_legal_class",
    # Tree cover
    "tree_cover": "existing_tree_cover_pct",
    "tree_cover_pct": "existing_tree_cover_pct",
    "canopy_cover": "existing_tree_cover_pct",
    "canopy_pct": "existing_tree_cover_pct",
    "existing_canopy": "existing_tree_cover_pct",
    # Planting status
    "planting": "planting_status",
    "planting_stage": "planting_status",
    "tree_planting_status": "planting_status",
    # Additionality
    "would_plant_without_carbon": "would_plant_anyway",
    "plant_without_carbon": "would_plant_anyway",
    "plant_anyway": "would_plant_anyway",
    "additionality": "would_plant_anyway",
    # Location
    "state": "location_state",
    "indian_state": "location_state",
    "land_state": "location_state",
    "district": "location_district",
    "land_district": "location_district",
    # Planting system
    "planting_type": "planting_system",
    "system": "planting_system",
    "tree_type": "planting_system",
    # Misc
    "legally_mandated": "planting_legally_mandated",
    "mandated": "planting_legally_mandated",
    "fra_claim": "fra_claim_flag",
    "registered_scheme": "existing_scheme_registration",
}

# Enum value alias maps: what users/admins might type → canonical enum values
_TENURE_ALIASES = {
    "owned outright": "owned", "self-owned": "owned", "owner": "owned",
    "i own it": "owned", "freehold": "owned",
    "government-granted": "government", "govt": "government",
    "panchayat": "community", "community/panchayat": "community",
    "community / panchayat land": "community",
    "community / panchayat": "community",
}
_LEGAL_CLASS_ALIASES = {
    "agricultural": "revenue_agricultural", "farm land": "revenue_agricultural",
    "revenue agricultural": "revenue_agricultural",
    "fallow": "revenue_fallow", "barren": "revenue_fallow",
    "revenue fallow / barren": "revenue_fallow",
    "forest": "recorded_forest", "reserved forest": "recorded_forest",
    "recorded forest area (rfa)": "recorded_forest",
    "grassland": "grassland_scrub", "scrubland": "grassland_scrub", "wasteland": "grassland_scrub",
    "grassland / scrubland": "grassland_scrub",
    "coastal": "coastal", "mangrove": "coastal",
}
_PLANTING_STATUS_ALIASES = {
    # Exact admin form labels (lowercase)
    "not started yet": "not_started",
    "planning to plant this year": "planned_this_year",
    "planted within the last 2 years": "planted_lt_2yrs",
    "planted within the last 2-5 years": "planted_2_5yrs",
    "planted more than 5 years ago": "planted_gt_5yrs",
    # Variants
    "not started": "not_started", "not yet": "not_started",
    "planning": "planned_this_year", "plan to plant": "planned_this_year",
    "planted recently": "planted_lt_2yrs", "just planted": "planted_lt_2yrs",
    "planted < 2 years ago": "planted_lt_2yrs",
    "planted 2-5 years": "planted_2_5yrs", "2 to 5 years ago": "planted_2_5yrs",
    "planted 2-5 years ago": "planted_2_5yrs", "planted in last 2-5 years": "planted_2_5yrs",
    "more than 5 years": "planted_gt_5yrs", "old plantation": "planted_gt_5yrs",
    "planted > 5 years ago": "planted_gt_5yrs",
}


def _fuzzy_planting_status(v: str) -> str:
    """Fuzzy-match a planting_status label to its enum value by checking key tokens."""
    # Check explicit alias map first
    mapped = _PLANTING_STATUS_ALIASES.get(v, None)
    if mapped:
        return mapped
    # Token-based fallback — avoids breaking on minor wording changes from admin panel
    if "not start" in v or v in ("no", "none"):
        return "not_started"
    if "this year" in v or ("plan" in v and "2" not in v and "5" not in v):
        return "planned_this_year"
    if "2-5" in v or "2 to 5" in v or "last 2-5" in v:
        return "planted_2_5yrs"
    if ("2 year" in v or "< 2" in v or "last 2 year" in v or "within the last 2 years" in v) and "5" not in v:
        return "planted_lt_2yrs"
    if "5" in v and ("more" in v or ">" in v or "old" in v or "gt" in v):
        return "planted_gt_5yrs"
    return v  # pass through to Pydantic — will raise a clear validation error


def _normalize_intake_fields(raw: dict) -> dict:
    """
    Maps arbitrary admin-form field_ids to canonical Tier1Intake field names.
    Also normalises common enum aliases so values are accepted by the Pydantic model.
    Uses fuzzy token matching for planting_status to be resilient to admin label changes.
    """
    normalized: dict = {}
    for k, v in raw.items():
        canonical_key = _FIELD_ALIASES.get(k.lower().strip(), k)
        # Normalise enum values
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if canonical_key == "tenure_type":
                v = _TENURE_ALIASES.get(v_lower, v_lower)
            elif canonical_key == "land_legal_class":
                v = _LEGAL_CLASS_ALIASES.get(v_lower, v_lower)
            elif canonical_key == "planting_status":
                v = _fuzzy_planting_status(v_lower)
            elif canonical_key == "would_plant_anyway":
                # Normalise yes/no/true/false strings to bool
                v = v_lower in ("yes", "true", "1", "y")
            elif canonical_key == "planting_legally_mandated":
                v = v_lower in ("yes", "true", "1", "y")
        normalized[canonical_key] = v

    # Inject rapid-screening defaults for Tier-2 fields that the UI form doesn't ask.
    # This prevents the rules engine from returning 'insufficient_information' for Gate 2 & 9.
    if "recent_clearing" not in normalized and "last_clearing_year" not in normalized:
        normalized["recent_clearing"] = False
    
    if "existing_scheme_registration" not in normalized:
        normalized["existing_scheme_registration"] = False
        
    return normalized

async def eligibility_agent(state: ConversationState) -> ConversationState:
    state["current_node"] = "ELIGIBILITY_AGENT"

    messages = state.get("messages", [])
    if not messages:
        return state

    last_user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if not last_user_msg:
        return state

    last_msg = last_user_msg.get("content", "")

    if not isinstance(state.get("intake_data"), dict):
        state["intake_data"] = {}

    # Fast path: form was just submitted
    if "eligibility_form" in last_msg:
        try:
            payload = json.loads(last_msg)
            if "eligibility_form" in payload:
                logger.info("Structured eligibility form received — skipping LLM, routing to verdict.")
                decision = EligibilityAgentDecision(next_action="run_verdict", reasoning="Form submitted")
        except Exception:
            # Fall back to LLM if JSON is malformed
            pass
    
    if "eligibility_form" not in last_msg:
        # LLM decides next action
        context_block = build_context_block(messages[:-1], conversation_summary=state.get("conversation_summary", ""), last_n=4)
        
        prompt = (
            f"{context_block}\n\n"
            f"State Flags:\n"
            f"- screening_started: {state.get('screening_started', False)}\n"
            f"- awaiting_eligibility_confirm: {state.get('awaiting_eligibility_confirm', False)}\n\n"
            f"User's message: \"{last_msg}\"\n\n"
            "Determine the next action for the Eligibility Agent."
        )

        try:
            decision = await llm_caller.call_with_schema(
                prompt=prompt,
                schema=EligibilityAgentDecision,
                system_prompt=AGENT_SYSTEM_PROMPT,
            )
            logger.info(f"Eligibility Agent LLM → {decision.next_action} ({decision.reasoning[:60]})")
        except Exception as e:
            logger.error(f"Eligibility decision failed: {e}")
            decision = EligibilityAgentDecision(next_action="passthrough", reasoning="Error fallback")

    # ── Execute Decision ──────────────────────────────────────────────────
    
    if decision.next_action == "show_form" or decision.next_action == "accept_confirm":
        state["awaiting_eligibility_confirm"] = False
        state["messages"].append({
            "role": "assistant",
            "content": decision.reply or "Great! Let me check your eligibility for carbon credits. Please fill out this short assessment form to get started."
        })
        state["ui_state"] = {
            "action": "SHOW_ELIGIBILITY_MODAL",
            "stage": "screening",
            "progress": 0,
        }
        return state

    elif decision.next_action == "search_and_offer":
        state["awaiting_eligibility_confirm"] = True
        reply_parts = []

        if decision.search_query:
            results = await _duckduckgo_search(decision.search_query)
            if results:
                search_context = _build_search_context(results)
                source_urls = [r.get("href", "") for r in results if r.get("href")]

                synth_prompt = (
                    f"User asked: {last_msg}\n\n"
                    f"Web Search Results:\n{search_context}\n\n"
                    "Synthesise a helpful, concise answer. Cite key sources."
                )
                try:
                    output = await llm_caller.call_with_schema(
                        prompt=synth_prompt,
                        schema=WebSearchAnswer,
                        system_prompt=WEB_ANSWER_SYSTEM,
                    )
                    reply_text = output.answer
                    if output.sources:
                        reply_text += "\n\n**Sources:**\n" + "\n".join(f"- {u}" for u in output.sources[:4])
                    elif source_urls:
                        reply_text += "\n\n**Sources:**\n" + "\n".join(f"- {u}" for u in source_urls[:4])
                    reply_text += f"\n\n_{output.disclaimer}_"
                    reply_parts.append(reply_text)
                except Exception as e:
                    logger.error(f"Search synthesis failed: {e}")

        reply_parts.append("\n\n**Would you like to check your own land's eligibility? I can run a quick assessment — just say Yes.**")

        state["messages"].append({
            "role": "assistant",
            "content": "\n".join(reply_parts).strip()
        })

        state["ui_state"] = {
            "action": "OFFER_ELIGIBILITY_CHECK"
        }
        return state

    elif decision.next_action == "run_verdict":
        state["screening_started"] = True
        state["awaiting_eligibility_confirm"] = False
        
        # Parse payload
        if "eligibility_form" in last_msg:
            try:
                payload = json.loads(last_msg)
                for k, v in payload["eligibility_form"].items():
                    state["intake_data"][k] = v
            except Exception:
                pass
                
        intake_raw = state["intake_data"]
        logger.info(f"Raw form data received: {intake_raw}")

        # Normalize field names: map admin form field_ids → Tier1Intake canonical names
        intake = _normalize_intake_fields(intake_raw) if isinstance(intake_raw, dict) else intake_raw
        logger.info(f"Normalized intake: {intake}")

        try:
            if isinstance(intake, Tier1Intake):
                intake_model = intake
            else:
                intake_model = Tier1Intake(**intake)
        except Exception as e:
            logger.error(f"Failed to parse intake data: {e}")
            # Still try with whatever we have, partial data is better than empty
            try:
                intake_model = Tier1Intake.model_construct(**intake)
            except Exception:
                intake_model = Tier1Intake()

        gate_results = []
        for gate_fn in GATES:
            try:
                result = gate_fn(intake_model)
                gate_results.append(result)
                if result.status == GateStatus.fail_structural:
                    logger.info(f"Gate '{result.gate_id}' — structural failure. Stopping.")
                    break
            except Exception as gate_err:
                logger.warning(f"Gate '{gate_fn.__name__}' error: {gate_err}")

        verdict = assemble_verdict(gate_results, intake_model)
        state["verdict"] = verdict
        logger.info(f"Verdict: {verdict.verdict} (confidence: {verdict.confidence})")

        # LLM explanation
        explain_prompt = (
            f"The rules engine has evaluated the user's land and produced:\n\n"
            f"Verdict Category: {verdict.verdict.value}\n"
            f"Confidence: {verdict.confidence}\n"
            f"Engine Reason: {verdict.confidence_reason}\n"
            f"Flags: {verdict.flags}\n"
            f"Knockout Gate (if any): {verdict.knockout_gate}\n\n"
            f"Land data: {json.dumps(intake, default=str)}\n\n"
            "Explain this verdict clearly and helpfully to the user."
        )
        try:
            explanation = await llm_caller.call_with_schema(
                prompt=explain_prompt,
                schema=ExplainOutput,
                system_prompt=EXPLAIN_SYSTEM,
            )
            state["messages"].append({"role": "assistant", "content": explanation.explanation})
        except Exception as e:
            logger.error(f"Explanation generation failed: {e}")
            state["messages"].append({
                "role": "assistant",
                "content": (
                    f"**Verdict: {verdict.verdict.value}**\n\n"
                    f"{verdict.confidence_reason}"
                ),
            })

        state["lead_score"] = _score_lead(verdict, intake)
        
        # Count fields roughly for UI
        total_fields = len(intake.keys()) if intake else 6
        
        state["ui_state"] = {
            "stage": "verdict_delivered",
            "progress": 1.0,
            "filled_fields": total_fields,
            "total_fields": total_fields,
            "show_memo_button": True,
            "verdict_category": verdict.verdict.value,
        }
        
        return state

    # passthrough
    return state
