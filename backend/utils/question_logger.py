"""
Unanswerable Question Logger — G7 Fix

The brief (§9.4) explicitly requires:
  "Log every unanswerable question. That log is the product roadmap."

This module provides a structured logging mechanism that writes to the
AuditLog DB table whenever the chatbot cannot answer a question confidently.
The admin panel will surface these as the knowledge gap backlog.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


async def log_unanswerable_question(
    session_id: Optional[str],
    question: str,
    node: str,
    reason: str,
    db: Optional[AsyncIOMotorDatabase] = None,
) -> None:
    """
    Log a question the bot could not answer to the AuditLog table.

    Args:
        session_id: The chat session ID.
        question: The user's question that could not be answered.
        node: Which orchestrator node encountered the limitation.
        reason: Why the question couldn't be answered (no context, out of scope, etc.)
        db: Async MongoDB database. If None, only logs to the application log.
    """
    payload = {
        "question": question,
        "node": node,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Always log to application log (useful even without DB)
    logger.info(
        f"[UNANSWERABLE] session={session_id} node={node} reason={reason} | "
        f"question={question[:120]}"
    )

    # Persist to DB if available
    if db is not None:
        try:
            entry = {
                "event_type": "unanswerable_question",
                "session_id": session_id,
                "assessment_id": None,
                "payload": payload,
                "ip_hash": None,
                "created_at": datetime.now(timezone.utc)
            }
            await db.audit_logs.insert_one(entry)
            logger.debug(f"Unanswerable question logged to AuditLog for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to write unanswerable question to AuditLog: {e}")
            # Non-fatal — the log above already captured it
