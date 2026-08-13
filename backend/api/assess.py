"""
POST /api/v1/assess — runs the deterministic rules engine and returns a verdict.
The LLM is NOT involved in the verdict — it only generates the explanation text.
"""

from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from typing import Optional
import secrets

from engine.schemas import Tier1Intake, Verdict
from engine.run_gates import run_gates
from llm.provider import llm_registry
from models.mongodb import get_db
from models.form_config import FormSchema, EvaluationConfig

router = APIRouter()

# System prompt given to the LLM — verdict field is read-only, passed in context
EXPLANATION_SYSTEM_PROMPT = """
You are EnviroWealth's Carbon Market Assistant. Your role is ONLY to:
1. Explain the eligibility verdict (already determined by the rules engine — do NOT change it)
2. Write clear, empathetic, plain-English explanations for Indian landholders
3. Surface the most important flags and next steps

STRICT RULES:
- You MUST NOT change the verdict or gate results
- You MUST NOT give legal, financial or investment advice
- You MUST NOT state specific methodology versions, prices, or fees from memory — only use what is provided in context
- Always end with the disclaimer: "This is a screening assessment only — not a legal or financial determination."
- Tone: warm, honest, direct. Not corporate. Not patronising.
"""


class AssessRequest(BaseModel):
    intake: Tier1Intake
    session_token: Optional[str] = None
    explain: bool = True   # whether to call LLM for plain-language explanation


class AssessResponse(BaseModel):
    session_token: str
    verdict: Verdict
    explanation: Optional[str] = None
    llm_model_used: Optional[str] = None


@router.get("/eligibility-form", response_model=FormSchema)
async def get_eligibility_form(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Fetch the dynamic eligibility form schema."""
    doc = await db.form_schemas.find_one({"schema_id": "default"})
    if not doc:
        return FormSchema()
    return FormSchema(**doc)



@router.post("/assess", response_model=AssessResponse)
async def assess(req: AssessRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Run the 10 eligibility gates and return a structured verdict.
    The verdict is always set by the rules engine — never by the LLM.
    """
    # Fetch dynamic rules
    config_doc = await db.evaluation_configs.find_one({"config_id": "default"})
    rules = EvaluationConfig(**config_doc).rules if config_doc else []

    # Run deterministic rules engine
    verdict, gate_results = run_gates(req.intake, rules)

    session_token = req.session_token or secrets.token_urlsafe(32)

    # Optional: call LLM for a plain-language explanation (not the verdict itself)
    explanation = None
    llm_model = None
    if req.explain:
        try:
            user_msg = f"""
The rules engine has produced the following eligibility assessment:
Verdict: {verdict.verdict.value}
Confidence: {verdict.confidence}
Confidence reason: {verdict.confidence_reason}
Flags: {verdict.flags}
Indicative numbers: {verdict.indicative_numbers.model_dump() if verdict.indicative_numbers else 'N/A'}
What we could not check: {verdict.what_we_could_not_check}
Next steps: {verdict.next_steps}
Alternatives: {verdict.alternatives}

Please write a clear, warm, plain-English explanation for the landholder.
Do not repeat the JSON — write it as a short, friendly summary (3–5 sentences).
"""
            resp = await llm_registry.generate_with_fallback(EXPLANATION_SYSTEM_PROMPT, user_msg)
            explanation = resp.content
            llm_model = resp.model_used
        except Exception as e:
            # LLM failure does not block the verdict — the deterministic result is always returned
            explanation = (
                f"[Plain-language explanation unavailable: {str(e)[:100]}. "
                f"The structured verdict above is still valid.]"
            )

    return AssessResponse(
        session_token=session_token,
        verdict=verdict,
        explanation=explanation,
        llm_model_used=llm_model,
    )
