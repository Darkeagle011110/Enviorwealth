"""
MongoDB async client — replaces models/database.py (SQLAlchemy).

Provides:
  - A single Motor AsyncIOMotorClient instance (app-lifetime singleton)
  - `get_db()` FastAPI dependency that yields the database object
  - `create_indexes()` called at startup to ensure all required indexes exist
  - TTL indexes on the sessions collection to auto-expire sessions (24 h)
    and rate-limit counters (1 h) — replaces Redis TTL behaviour
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import CollectionInvalid

from config.settings import settings

logger = logging.getLogger(__name__)

# ── Singleton client ──────────────────────────────────────────────────────────
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_url)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = get_client()[settings.mongodb_db_name]
    return _db


async def close_client():
    """Call at application shutdown."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
    logger.info("MongoDB client closed.")


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    FastAPI dependency — yields the MongoDB database.
    Usage: `db: AsyncIOMotorDatabase = Depends(get_db)`
    """
    yield get_database()


# ── Index creation ────────────────────────────────────────────────────────────
async def create_indexes():
    """
    Idempotently create all required MongoDB indexes.
    Called once at app startup.
    """
    db = get_database()

    # ── client_users ─────────────────────────────────────────────────────────
    await db.client_users.create_indexes([
        IndexModel([("email", ASCENDING)], unique=True, name="uq_email"),
    ])

    # ── assessment_sessions ───────────────────────────────────────────────────
    await db.assessment_sessions.create_indexes([
        IndexModel([("session_token", ASCENDING)], unique=True, name="uq_session_token"),
        IndexModel([("user_id", ASCENDING)], name="idx_user_id"),
        IndexModel([("created_at", DESCENDING)], name="idx_created_at"),
    ])

    # ── gate_results ──────────────────────────────────────────────────────────
    await db.gate_results.create_indexes([
        IndexModel([("session_id", ASCENDING)], name="idx_gr_session_id"),
    ])

    # ── assessments ───────────────────────────────────────────────────────────
    await db.assessments.create_indexes([
        IndexModel([("session_id", ASCENDING)], name="idx_ass_session_id"),
        IndexModel([("verdict", ASCENDING)], name="idx_verdict"),
        IndexModel([("created_at", DESCENDING)], name="idx_ass_created_at"),
    ])

    # ── leads ─────────────────────────────────────────────────────────────────
    await db.leads.create_indexes([
        IndexModel([("session_id", ASCENDING)], name="idx_lead_session_id"),
        IndexModel([("assessment_id", ASCENDING)], name="idx_lead_assessment_id"),
        IndexModel([("lead_score", ASCENDING), ("status", ASCENDING)], name="idx_lead_score_status"),
        IndexModel([("email", ASCENDING)], name="idx_lead_email"),
        IndexModel([("mobile", ASCENDING)], name="idx_lead_mobile"),
        IndexModel([("created_at", DESCENDING)], name="idx_lead_created_at"),
    ])

    # ── audit_logs ────────────────────────────────────────────────────────────
    await db.audit_logs.create_indexes([
        IndexModel([("event_type", ASCENDING), ("created_at", DESCENDING)], name="idx_audit_event"),
        IndexModel([("session_id", ASCENDING)], name="idx_audit_session"),
    ])

    # ── llm_provider_configs ──────────────────────────────────────────────────
    await db.llm_provider_configs.create_indexes([
        IndexModel([("is_active", ASCENDING)], name="idx_llm_active"),
        IndexModel([("is_fallback", ASCENDING)], name="idx_llm_fallback"),
    ])

    # ── knowledge_documents ───────────────────────────────────────────────────
    await db.knowledge_documents.create_indexes([
        IndexModel([("is_active", ASCENDING)], name="idx_doc_active"),
        IndexModel([("file_hash", ASCENDING)], name="idx_doc_hash"),
        IndexModel([("created_at", DESCENDING)], name="idx_doc_created_at"),
    ])

    # ── knowledge_chunks (for admin display / reference) ─────────────────────
    await db.knowledge_chunks.create_indexes([
        IndexModel([("document_id", ASCENDING)], name="idx_chunk_doc_id"),
        IndexModel([("document_id", ASCENDING), ("chunk_index", ASCENDING)],
                   unique=True, name="uq_chunk_doc_idx"),
    ])

    # ── sessions (replaces Redis) ─────────────────────────────────────────────
    # TTL index: documents automatically deleted after `expires_at` field time
    await db.sessions.create_indexes([
        IndexModel([("_id", ASCENDING)], name="idx_session_id"),
        # TTL index — MongoDB auto-deletes docs when expires_at is in the past
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_session_expires"),
    ])

    # ── rate_limits (replaces Redis rate limiting) ────────────────────────────
    await db.rate_limits.create_indexes([
        IndexModel([("_id", ASCENDING)], name="idx_rl_id"),
        # TTL index: each rate-limit doc expires after 1 hour automatically
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_rl_expires"),
    ])

    # ── form_schemas ──────────────────────────────────────────────────────────
    await db.form_schemas.create_indexes([
        IndexModel([("schema_id", ASCENDING)], unique=True, name="uq_form_schema_id"),
    ])

    # ── evaluation_configs ────────────────────────────────────────────────────
    await db.evaluation_configs.create_indexes([
        IndexModel([("config_id", ASCENDING)], unique=True, name="uq_eval_config_id"),
    ])

    logger.info("MongoDB indexes created successfully.")
