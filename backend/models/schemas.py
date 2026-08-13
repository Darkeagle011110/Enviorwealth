"""
MongoDB document schemas — Pydantic models that define the shape of each
MongoDB collection document. These replace the old SQLAlchemy ORM models.

Design notes:
  - `_id` in MongoDB maps to the `id` field here (stored as a str UUID)
  - All datetime fields are UTC-aware
  - JSONB fields from Postgres become plain `dict` or `list` fields
  - References between collections use string UUIDs (no foreign-key enforcement
    at DB level — enforced at application layer)
"""

from __future__ import annotations

from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# ── LLM Provider Config ───────────────────────────────────────────────────────
class LLMProviderConfigDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    is_active: bool = False
    is_fallback: bool = False
    provider: str                    # claude | openai | groq | gemini
    model_name: str
    api_key_enc: str                 # Fernet-encrypted at application layer
    extra_params: Dict[str, Any] = {}
    last_tested_at: Optional[datetime] = None
    last_test_ok: Optional[bool] = None
    last_test_ms: Optional[int] = None
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ── Knowledge Corpus (RAG) ────────────────────────────────────────────────────
class KnowledgeDocumentDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    title: str
    version: Optional[str] = None
    publication_date: Optional[str] = None   # ISO date string
    effective_date: Optional[str] = None     # ISO date string
    jurisdiction: Optional[str] = None
    doc_type: Optional[str] = None
    standard_body: Optional[str] = None
    file_path: Optional[str] = None
    file_hash: Optional[str] = None
    retrieval_date: Optional[str] = None     # ISO date string
    is_active: bool = True
    superseded_by: Optional[str] = None      # id of newer document
    source_url: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class KnowledgeChunkDoc(BaseModel):
    """
    Stored in MongoDB for reference / admin display.
    The actual embedding vector lives in Qdrant (same `id` as the Qdrant point).
    """
    id: str = Field(default_factory=_new_id)
    document_id: str
    chunk_index: int
    content: str
    doc_summary: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=_now)


# ── Client Users ──────────────────────────────────────────────────────────────
class ClientUserDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    email: str
    password_hash: str
    full_name: str
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ── Assessment Sessions ───────────────────────────────────────────────────────
class AssessmentSessionDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    user_id: Optional[str] = None
    session_token: str
    tier: int = 1
    intake_data: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class GateResultDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    session_id: str
    gate_id: str
    status: str
    reason: str
    redirect: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=_now)


class AssessmentDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    session_id: str
    verdict: str
    confidence: Optional[str] = None
    confidence_reason: Optional[str] = None
    knockout_gate: Optional[str] = None
    flags: List[Any] = []
    indicative_data: Dict[str, Any] = {}
    what_we_could_not_check: List[Any] = []
    next_steps: List[Any] = []
    alternatives: List[Any] = []
    raw_gate_results: List[Any] = []
    llm_model_used: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


# ── Leads ─────────────────────────────────────────────────────────────────────
class LeadDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    session_id: Optional[str] = None
    assessment_id: Optional[str] = None
    name: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    state: Optional[str] = None
    preferred_contact: Optional[str] = None
    consent_given: bool = False
    lead_score: Optional[str] = None
    score_reason: Dict[str, Any] = {}
    status: str = "new"
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ── Audit Log ─────────────────────────────────────────────────────────────────
class AuditLogDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    event_type: str
    session_id: Optional[str] = None
    assessment_id: Optional[str] = None
    payload: Dict[str, Any] = {}
    ip_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
