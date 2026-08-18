"""
crm_sync.py — Syncs conversation state to MongoDB CRM tables.

Fixes applied:
- FIX 4: Saves messages permanently to assessment_sessions.messages
  so the lead detail view and session restore don't rely on the 24hr
  ephemeral sessions TTL collection.
- FIX 9: Added retry logic (3 attempts with exponential backoff) for
  transient DB failures — previously fire-and-forget with no retry.
"""

import asyncio
import logging
from typing import Optional
from models.mongodb import get_database

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 2.0


async def _sync_with_retry(session_id: str, state_dict: dict, user_id=None, user_name="Anonymous User"):
    """Inner sync with retry logic."""
    db = get_database()

    # 1. Update or Create AssessmentSession — now also saves messages permanently
    messages = state_dict.get("messages", [])
    # Sanitise messages for permanent storage (replace raw JSON form payloads)
    clean_messages = []
    for msg in messages:
        content = msg.get("content", "")
        if msg.get("role") == "user" and '"eligibility_form"' in content:
            clean_messages.append({
                "role": "user",
                "content": "📋 Submitted Eligibility Assessment Form",
            })
        else:
            clean_messages.append({"role": msg.get("role"), "content": content})

    db_session = await db.assessment_sessions.find_one({"session_token": session_id})
    if not db_session:
        from datetime import datetime, timezone
        # IMPORTANT: user_id MUST be stored as a string (not ObjectId) to match
        # the query in api/chat.py get_user_sessions which uses str(current_user.id)
        user_id_str = str(user_id) if user_id is not None else None
        new_session = {
            "session_token": session_id,
            "user_id": user_id_str,
            "tier": 1,
            "intake_data": state_dict.get("intake_data", {}),
            "messages": clean_messages,  # permanently stored
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        res = await db.assessment_sessions.insert_one(new_session)
        session_doc_id = str(res.inserted_id)
    else:
        session_doc_id = str(db_session.get("_id") or db_session.get("id"))
        from datetime import datetime, timezone
        update_fields = {
            "intake_data": state_dict.get("intake_data", {}),
            "messages": clean_messages,  # ← FIX 4: keep messages in sync
            "tier": 1,
            "updated_at": datetime.now(timezone.utc),
        }
        # Always sync user_id so sessions created before login get linked
        if user_id is not None:
            update_fields["user_id"] = str(user_id)
        await db.assessment_sessions.update_one(
            {"session_token": session_id},
            {"$set": update_fields}
        )

    # 2. If verdict exists, save Assessment
    verdict = state_dict.get("verdict")
    assessment_doc_id = None
    if verdict:
        db_assessment = await db.assessments.find_one({"session_id": session_doc_id})

        if isinstance(verdict, dict):
            v_cat = verdict.get("verdict")
            confidence = verdict.get("confidence")
            knockout_gate = verdict.get("knockout_gate")
            flags = verdict.get("flags", [])
        else:
            v_cat = getattr(verdict, "verdict", None)
            if v_cat and hasattr(v_cat, "value"):
                v_cat = v_cat.value
            confidence = getattr(verdict, "confidence", None)
            knockout_gate = getattr(verdict, "knockout_gate", None)
            flags = getattr(verdict, "flags", [])

        update_data = {
            "verdict": v_cat or "UNKNOWN",
            "confidence": confidence,
            "knockout_gate": knockout_gate,
            "flags": flags,
        }

        if not db_assessment:
            from datetime import datetime, timezone
            update_data["session_id"] = session_doc_id
            update_data["created_at"] = datetime.now(timezone.utc)
            res = await db.assessments.insert_one(update_data)
            assessment_doc_id = str(res.inserted_id)
        else:
            assessment_doc_id = str(db_assessment.get("_id") or db_assessment.get("id"))
            await db.assessments.update_one(
                {"session_id": session_doc_id},
                {"$set": update_data}
            )

    # 3. If lead_score exists, save Lead
    lead_score = state_dict.get("lead_score")
    if lead_score and assessment_doc_id:
        db_lead = await db.leads.find_one({"session_id": session_doc_id})

        intake = state_dict.get("intake_data", {})
        lead_update = {"lead_score": lead_score}

        if not db_lead:
            from datetime import datetime, timezone
            lead_update["session_id"] = session_doc_id
            lead_update["assessment_id"] = assessment_doc_id
            lead_update["state"] = intake.get("location_state") or intake.get("state", "Unknown")
            lead_update["name"] = user_name
            lead_update["status"] = "new"
            lead_update["created_at"] = datetime.now(timezone.utc)
            lead_update["updated_at"] = datetime.now(timezone.utc)
            await db.leads.insert_one(lead_update)
        else:
            if not db_lead.get("state"):
                lead_update["state"] = intake.get("location_state") or intake.get("state", "Unknown")
            if not db_lead.get("name"):
                lead_update["name"] = user_name
            if not db_lead.get("status"):
                lead_update["status"] = "new"

            from datetime import datetime, timezone
            lead_update["updated_at"] = datetime.now(timezone.utc)

            await db.leads.update_one(
                {"session_id": session_doc_id},
                {"$set": lead_update}
            )


async def sync_state_to_crm(session_id: str, state_dict: dict, user_id=None, user_name="Anonymous User"):
    """
    Syncs the current conversation state into the MongoDB CRM tables.
    Retries up to 3 times on transient DB failures.
    """
    last_error = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            await _sync_with_retry(session_id, state_dict, user_id, user_name)
            return  # success
        except Exception as e:
            last_error = e
            if attempt < _MAX_RETRIES:
                delay = _RETRY_DELAY_SECONDS * attempt  # 2s, 4s, 6s
                logger.warning(
                    f"CRM sync attempt {attempt}/{_MAX_RETRIES} failed for session "
                    f"{session_id}: {e}. Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"CRM sync permanently failed after {_MAX_RETRIES} attempts for "
                    f"session {session_id}: {last_error}"
                )
