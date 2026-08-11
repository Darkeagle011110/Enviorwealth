"""
SQLAlchemy ORM models mirroring the init.sql schema.
"""

from datetime import datetime, date
from typing import Optional, List
import uuid

from sqlalchemy import (
    Column, String, Boolean, Integer, Text, Float,
    DateTime, Date, JSON, ForeignKey, UniqueConstraint, Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, DeclarativeBase
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────────────────────────────────────
# LLM Provider Configuration
# ──────────────────────────────────────────────────────────────────────────────
class LLMProviderConfig(Base):
    __tablename__ = "llm_provider_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    is_active = Column(Boolean, nullable=False, default=False)
    is_fallback = Column(Boolean, nullable=False, default=False)
    provider = Column(String(20), nullable=False)      # claude | openai | groq | gemini
    model_name = Column(String(100), nullable=False)
    api_key_enc = Column(Text, nullable=False)
    extra_params = Column(JSONB, default={})
    last_tested_at = Column(DateTime(timezone=True))
    last_test_ok = Column(Boolean)
    last_test_ms = Column(Integer)
    updated_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ──────────────────────────────────────────────────────────────────────────────
# Knowledge Corpus (RAG)
# ──────────────────────────────────────────────────────────────────────────────
class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    version = Column(String(50))
    publication_date = Column(Date)
    effective_date = Column(Date)
    jurisdiction = Column(String(100))
    doc_type = Column(String(50))
    standard_body = Column(String(100))
    file_path = Column(Text)
    file_hash = Column(String(64))
    retrieval_date = Column(Date, default=date.today)
    is_active = Column(Boolean, nullable=False, default=True)
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id"))
    source_url = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    doc_summary = Column(Text)
    embedding = Column(Vector(384))               # matches all-MiniLM-L6-v2
    metadata_ = Column("metadata", JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_doc_chunk"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Client Users
# ──────────────────────────────────────────────────────────────────────────────
class ClientUser(Base):
    __tablename__ = "client_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    full_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    sessions = relationship("AssessmentSession", back_populates="user", cascade="all, delete-orphan")


# ──────────────────────────────────────────────────────────────────────────────
# Assessment Sessions & Gate Results
# ──────────────────────────────────────────────────────────────────────────────
class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("client_users.id", ondelete="CASCADE"))
    session_token = Column(String(128), unique=True, nullable=False)
    tier = Column(Integer, nullable=False, default=1)
    intake_data = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("ClientUser", back_populates="sessions")
    gate_results = relationship("GateResultRecord", back_populates="session", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="session", cascade="all, delete-orphan")


class GateResultRecord(Base):
    __tablename__ = "gate_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("assessment_sessions.id", ondelete="CASCADE"), nullable=False)
    gate_id = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False)
    reason = Column(Text, nullable=False)
    redirect = Column(Text)
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("AssessmentSession", back_populates="gate_results")


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("assessment_sessions.id", ondelete="CASCADE"), nullable=False)
    verdict = Column(String(40), nullable=False)
    confidence = Column(String(10))
    confidence_reason = Column(Text)
    knockout_gate = Column(String(20))
    flags = Column(JSONB, default=[])
    indicative_data = Column(JSONB, default={})
    what_we_could_not_check = Column(JSONB, default=[])
    next_steps = Column(JSONB, default=[])
    alternatives = Column(JSONB, default=[])
    raw_gate_results = Column(JSONB, default=[])
    llm_model_used = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("AssessmentSession", back_populates="assessments")


# ──────────────────────────────────────────────────────────────────────────────
# Leads
# ──────────────────────────────────────────────────────────────────────────────
class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("assessment_sessions.id"))
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("assessments.id"))
    name = Column(String(200))
    mobile = Column(String(20))
    email = Column(String(200))
    state = Column(String(100))
    preferred_contact = Column(String(20))
    consent_given = Column(Boolean, nullable=False, default=False)
    lead_score = Column(String(20))
    score_reason = Column(JSONB, default={})
    status = Column(String(30), default="new")
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ──────────────────────────────────────────────────────────────────────────────
# Audit Log
# ──────────────────────────────────────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)
    session_id = Column(UUID(as_uuid=True))
    assessment_id = Column(UUID(as_uuid=True))
    payload = Column(JSONB, default={})
    ip_hash = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
