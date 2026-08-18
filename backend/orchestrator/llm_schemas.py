"""
llm_schemas.py — Pydantic schemas for structured LLM outputs.

Simplified for the 4-agent architecture:
- OrchestratorRoute: 3 options (was 10) — much more reliable structured output
- FieldExtraction: unchanged — used by eligibility_agent
- ExplainOutput: unchanged — used by eligibility_agent
- FactualAnswer, AgenticCriticOutput: kept for compatibility (used in tests)
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# ─── Orchestrator routing (Tier-3 LLM fallback) ───────────────────────────────

class OrchestratorDecision(BaseModel):
    """
    The Orchestrator's LLM decision output.
    Either routes to a sub-agent OR provides a direct inline reply.
    """
    route_to: str = Field(
        ...,
        description=(
            "Must be exactly one of: "
            "'rag' (user needs factual info from the carbon credit knowledge base), "
            "'eligibility' (user wants to check eligibility of something), "
            "'inline' (you answer this yourself — greetings, simple Qs, out-of-domain, refusals)"
        ),
    )
    reply: str = Field(
        default="",
        description=(
            "Your direct answer to the user. ONLY provide this when route_to is 'inline'. "
            "Leave empty when routing to rag or eligibility."
        ),
    )
    reasoning: str = Field(..., description="Brief reasoning for this routing decision.")


# ─── Field extraction for eligibility intake ──────────────────────────────────

class FieldExtraction(BaseModel):
    """Extracts unstructured user answers into specific Tier-1 intake schema fields."""
    area_ha: Optional[float] = None
    tenure_type: Optional[str] = Field(
        None, description="owned | leased | government | community | disputed | unknown"
    )
    land_legal_class: Optional[str] = None
    existing_tree_cover_pct: Optional[float] = None
    land_use_10yr_ago: Optional[str] = None
    planting_status: Optional[str] = None
    planting_system: Optional[str] = None
    would_plant_anyway: Optional[bool] = None
    planting_legally_mandated: Optional[bool] = None
    already_profitable_without_carbon: Optional[bool] = None
    recent_clearing: Optional[bool] = None
    last_clearing_year: Optional[int] = None
    existing_scheme_registration: Optional[bool] = None
    lease_years_remaining: Optional[int] = None
    fra_claim_flag: Optional[bool] = None
    grazing_use: Optional[bool] = None
    location_state: Optional[str] = None

    # Internal reasoning for transparency
    extraction_confidence: str = Field(..., description="high | medium | low")
    assumptions_made: Optional[str] = Field(
        None, description="Any assumptions made during extraction"
    )


# ─── Verdict explanation ───────────────────────────────────────────────────────

class ExplainOutput(BaseModel):
    """
    Plain-English explanation of the verdict.
    The LLM must NOT change the verdict — only explain it.
    """
    explanation: str = Field(
        ..., description="Plain-English explanation of the gate results and verdict."
    )
    clarifying_question: Optional[str] = Field(
        None, description="The single next question to ask, if needed (e.g. Tier-2 refinement)."
    )
    tone_note: str = Field(
        ..., description="Tone used: 'empathetic' | 'direct' | 'cautionary'"
    )
    confidence_level: str = Field(
        ..., description="'high' | 'medium' | 'low' based on the engine's assessment."
    )


# ─── Kept for backward compatibility / tests ──────────────────────────────────

class FactualAnswer(BaseModel):
    """Single-pass RAG factual answer (kept for test compatibility)."""
    answer: str = Field(..., description="The factual answer to the user's question.")
    source_chunk_ids: List[str] = Field(default_factory=list)
    last_verified_date: Optional[str] = Field(None)
    disclaimer: str = Field(
        ..., description="Standard disclaimer — educational info, not legal/financial advice."
    )


class AgenticCriticOutput(BaseModel):
    """Agentic RAG critic evaluation (kept for test compatibility)."""
    is_grounded: bool = Field(
        ..., description="True if context fully answers the question."
    )
    missing_information: Optional[str] = Field(None)
    revised_search_query: Optional[str] = Field(None)


# ─── Legacy alias — do not remove (turn_router tests may reference TurnRoute) ──

class TurnRoute(BaseModel):
    """
    Legacy router schema. Kept for test compatibility only.
    New code should use OrchestratorRoute.
    """
    route_type: str = Field(
        ...,
        description=(
            "One of: 'rag', 'eligibility', 'out_of_domain'"
        ),
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reasoning: str = Field(default="")
