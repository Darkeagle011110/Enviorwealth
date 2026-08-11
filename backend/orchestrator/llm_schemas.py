from typing import List, Optional
from pydantic import BaseModel, Field


class TurnRoute(BaseModel):
    """Router classification for the next turn type."""
    route_type: str = Field(
        ...,
        description=(
            "Must be exactly one of: 'consult', 'start_screening', 'intake_answer', "
            "'factual_question', 'edge_case', 'offer_review', 'out_of_scope_legal', "
            "'out_of_scope_guarantee', 'green_credit_correction', 'scepticism_handling'"
        )
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str


class FieldExtraction(BaseModel):
    """Extracts unstructured user answers into specific schema fields."""
    area_ha: Optional[float] = None
    tenure_type: Optional[str] = Field(None, description="owned, leased, government, community, disputed, unknown")
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
    
    # Internal reasoning for transparency
    extraction_confidence: str = Field(..., description="high, medium, low")
    assumptions_made: Optional[str] = Field(None, description="Any assumptions made during extraction")


class ExplainOutput(BaseModel):
    """
    Plain English explanation of the verdict, next steps, and missing info.
    NOTE: The `verdict` field is deliberately excluded here. The LLM must not 
    decide the verdict, only explain the one provided in its context.
    """
    explanation: str = Field(..., description="Plain-English explanation of the gate results and verdict.")
    clarifying_question: Optional[str] = Field(None, description="The single next question to ask, if any.")
    tone_note: str = Field(..., description="Tone used: 'empathetic', 'direct', or 'cautionary'.")
    confidence_level: str = Field(..., description="'high', 'medium', or 'low' based on the engine's assessment.")


class FactualAnswer(BaseModel):
    """Single-pass RAG factual answer."""
    answer: str = Field(..., description="The factual answer to the user's question.")
    source_chunk_ids: List[str] = Field(default_factory=list, description="IDs of the chunks used to answer.")
    last_verified_date: Optional[str] = Field(None, description="The most recent verification date from the chunks used.")
    disclaimer: str = Field(..., description="A standard disclaimer that this is educational info, not legal/financial advice.")


class AgenticCriticOutput(BaseModel):
    """Agentic RAG critic evaluation of retrieved context."""
    is_grounded: bool = Field(..., description="True if the context fully answers the question, False otherwise.")
    missing_information: Optional[str] = Field(None, description="What specific information is still missing?")
    revised_search_query: Optional[str] = Field(None, description="If not grounded, a better search query to try.")
