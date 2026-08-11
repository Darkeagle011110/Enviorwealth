import logging
from orchestrator.state import ConversationState
from orchestrator.llm_schemas import FieldExtraction
from orchestrator.llm_caller import llm_caller
from engine.schemas import Tier1Intake
from geospatial.geo_service import geo_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a data extraction assistant for a carbon credit eligibility chatbot.
Extract fields from the user's message to fill the carbon credit eligibility form.

RULES:
- Map the user's answer to the corresponding field.
- If the user says "I don't know", "unsure", "not sure" — set the field to null (do not guess).
- Accept local Indian land area units: 1 acre = 0.405 ha, 1 bigha ≈ 0.13–0.67 ha (assume 0.25 ha if state unknown), 1 gunta = 0.025 ha.
- Convert all area to hectares in area_ha.
- Be liberal in matching: "I own it" → tenure_type = "owned", "government land" → "government", etc.
"""

# C6 FIX: All 6 mandatory Tier-1 fields are now collected.
# Previously missing: existing_tree_cover_pct (Gate 1) and would_plant_anyway (Gate 4).
# Each question includes a "why" clause as required by §9.2 of the brief.
REQUIRED_FIELDS = [
    (
        "area_ha",
        "How large is the land you want to assess? You can give the area in hectares, acres, bigha, or gunta — I'll convert it. "
        "*(This matters because the economics of carbon projects depend heavily on scale — most methodologies require a minimum area.)*"
    ),
    (
        "tenure_type",
        "What is your land ownership or tenure status? For example: owned outright, leased, community/panchayat land, government-granted, or disputed. "
        "*(Tenure affects who holds the carbon rights — the landowner must be able to make a 30-year commitment.)*"
    ),
    (
        "land_legal_class",
        "What is the official legal classification of your land? For example: revenue fallow, revenue agricultural, recorded forest, grassland or scrubland, wasteland, or private forest. "
        "*(This is the single biggest eligibility determinant — planting on recorded forest land is ineligible under all current methodologies.)*"
    ),
    (
        "existing_tree_cover_pct",
        "Roughly what percentage of your land currently has tree cover (canopy coverage)? Even a rough estimate like 10%, 30%, or 60% is fine. "
        "*(Carbon credits only count newly added tree cover. If the land already has dense forest, there is little room for additionality — this is Gate 1 of our eligibility check.)*"
    ),
    (
        "planting_status",
        "Have you already started planting trees on this land? Options: not started yet, planning to plant this year, planted within the last 2–5 years, or planted more than 5 years ago. "
        "*(If trees were planted before 2019, they fall outside the crediting window of current Indian carbon methodologies.)*"
    ),
    (
        "would_plant_anyway",
        "Would you plant trees on this land even if there were no carbon credit income? Please answer yes or no. "
        "*(This is the additionality test — carbon credits are only given for planting that would NOT have happened without the carbon incentive. Answering yes doesn't disqualify you, but it does reduce confidence.)*"
    ),
]


async def screen_node(state: ConversationState) -> ConversationState:
    """
    Handles the TIER1_SCREEN state. Extracts fields from the latest message,
    updates the intake data, and determines the next question to ask.
    Completes progressive disclosure for all 6 mandatory Tier-1 fields.
    """
    state["current_node"] = "TIER1_SCREEN"

    # 1. Extract data if there's a new user message
    if state.get("messages") and state["messages"][-1]["role"] == "user":
        last_msg = state["messages"][-1]["content"]

        # Check if the frontend sent the structured UI form payload
        if "eligibility_form" in last_msg:
            try:
                import json
                payload = json.loads(last_msg)
                if "eligibility_form" in payload:
                    logger.info("Received structured eligibility form payload. Bypassing LLM extraction.")
                    if not isinstance(state.get("intake_data"), dict):
                        state["intake_data"] = {}
                    
                    form_data = payload["eligibility_form"]
                    # Map the form data to intake_data
                    for k, v in form_data.items():
                        state["intake_data"][k] = v
                        
                    last_msg = "" # Clear it so LLM extraction isn't run
            except Exception as e:
                logger.error(f"Failed to parse eligibility form payload: {e}")

        # Check if the frontend sent a polygon payload
        if "polygon" in last_msg.lower() or "geojson" in last_msg.lower():
            try:
                import json
                payload = json.loads(last_msg)
                if "polygon" in payload:
                    logger.info("Polygon received. Fetching geospatial data...")
                    geo_data = await geo_service.get_all_geo_data(payload["polygon"])

                    if not isinstance(state.get("intake_data"), dict):
                        state["intake_data"] = {}

                    state["intake_data"].update(geo_data)

                    tree_cover = geo_data.get("existing_tree_cover_pct", "unknown")
                    state["messages"].append({
                        "role": "assistant",
                        "content": (
                            f"📡 Based on satellite data (Google Earth Engine), I can see your parcel has approximately "
                            f"**{tree_cover}% tree cover**. I've used this to fill in that field automatically.\n\n"
                            f"Does that look roughly correct from your experience on the ground?"
                        )
                    })
                    last_msg = ""
            except Exception as e:
                logger.error(f"Failed to process polygon: {e}")

        if last_msg:
            context_q = state.get("current_question", "")

            prompt = (
                f"Question that was just asked: {context_q}\n"
                f"User's reply: {last_msg}\n\n"
                f"Extract all relevant fields from this reply."
            )

            try:
                extraction = await llm_caller.call_with_schema(
                    prompt=prompt,
                    schema=FieldExtraction,
                    system_prompt=SYSTEM_PROMPT
                )

                extracted_dict = extraction.dict(
                    exclude_none=True,
                    exclude={"extraction_confidence", "assumptions_made"}
                )

                if not isinstance(state.get("intake_data"), dict):
                    state["intake_data"] = {}

                for k, v in extracted_dict.items():
                    state["intake_data"][k] = v

                if extraction.assumptions_made:
                    logger.info(f"Extraction assumptions: {extraction.assumptions_made}")

            except Exception as e:
                logger.error(f"Field extraction failed: {e}")

    # 2. Determine what's still missing
    intake = state.get("intake_data", {}) or {}
    missing_fields = []
    next_question = None

    for field_name, question_text in REQUIRED_FIELDS:
        if field_name not in intake or intake.get(field_name) is None:
            missing_fields.append(field_name)
            if not next_question:
                next_question = question_text
                state["current_question"] = next_question

    state["missing_fields"] = missing_fields

    total_fields = len(REQUIRED_FIELDS)
    filled_fields = total_fields - len(missing_fields)

    # 3. Ask next question or trigger UI form
    if next_question:
        # If we have absolutely no data yet, trigger the modal UI instead of asking the first question
        if not intake:
            state["messages"].append({
                "role": "assistant",
                "content": "Let's check your land eligibility! Please fill out this short assessment form."
            })
            state["ui_state"] = {
                "action": "SHOW_ELIGIBILITY_MODAL",
                "stage": "screening",
                "progress": 0,
            }
        else:
            state["messages"].append({"role": "assistant", "content": next_question})
            state["ui_state"] = {
                "stage": "screening",
                "progress": filled_fields / total_fields,
                "filled_fields": filled_fields,
                "total_fields": total_fields,
                "current_field": missing_fields[0] if missing_fields else None,
            }
    else:
        # All 6 Tier-1 fields collected — trigger the rules engine
        state["route_type"] = "ready_for_verdict"
        state["ui_state"] = {
            "stage": "ready_for_verdict",
            "progress": 1.0,
            "filled_fields": total_fields,
            "total_fields": total_fields,
        }

    return state
