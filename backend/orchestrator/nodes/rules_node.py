"""
Rules Node — runs the deterministic 10-gate eligibility pipeline.

FIX (Critical): Previously called run_gates(intake_model) with an empty
rules list, so every submission produced a blanket "pass" verdict regardless
of the user's land data. Now calls the GATES pipeline from gates.py directly.
"""

import logging
from orchestrator.state import ConversationState
from engine.schemas import Tier1Intake
from engine.gates import GATES
from engine.verdict import assemble_verdict
from engine.schemas import GateStatus

logger = logging.getLogger(__name__)


def rules_node(state: ConversationState) -> ConversationState:
    """
    Handles the TIER1_VERDICT state.
    Runs the deterministic 10-gate pipeline (gates.py → GATES) to produce a verdict.
    """
    state["current_node"] = "TIER1_VERDICT"

    # 1. Convert state dict to Typed Pydantic model
    try:
        intake_data = state.get("intake_data", {})
        if isinstance(intake_data, Tier1Intake):
            intake_model = intake_data
        else:
            intake_model = Tier1Intake(**intake_data)
    except Exception as e:
        logger.error(f"Failed to parse intake data for rules engine: {e}")
        intake_model = Tier1Intake()

    # 2. Run the 10-gate pipeline in sequence; short-circuit on structural failure
    gate_results = []
    for gate_fn in GATES:
        try:
            result = gate_fn(intake_model)
            gate_results.append(result)
            if result.status == GateStatus.fail_structural:
                logger.info(
                    f"Gate '{result.gate_id}' produced structural failure — "
                    "stopping evaluation early."
                )
                break
        except Exception as gate_err:
            logger.warning(f"Gate '{gate_fn.__name__}' raised an error: {gate_err}")

    # 3. Assemble verdict from gate results
    verdict = assemble_verdict(gate_results, intake_model)
    logger.info(f"Verdict: {verdict.verdict} (confidence: {verdict.confidence})")

    # 4. Save to state
    state["verdict"] = verdict

    return state
