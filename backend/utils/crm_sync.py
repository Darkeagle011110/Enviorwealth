import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from models.mongodb import get_database

logger = logging.getLogger(__name__)

async def sync_state_to_crm(session_id: str, state_dict: dict, user_id=None, user_name="Anonymous User"):
    """
    Syncs the current conversation state into the MongoDB tables.
    """
    try:
        db = get_database()
        
        # 1. Update or Create AssessmentSession
        db_session = await db.assessment_sessions.find_one({"session_token": session_id})
        if not db_session:
            from datetime import datetime, timezone
            new_session = {
                "session_token": session_id,
                "user_id": user_id,
                "tier": 1,
                "intake_data": state_dict.get("intake_data", {}),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            res = await db.assessment_sessions.insert_one(new_session)
            session_doc_id = str(res.inserted_id)
        else:
            session_doc_id = str(db_session.get("_id") or db_session.get("id"))
            from datetime import datetime, timezone
            await db.assessment_sessions.update_one(
                {"session_token": session_id},
                {"$set": {
                    "intake_data": state_dict.get("intake_data", {}),
                    "tier": 1,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
        
        # 2. If verdict exists, save Assessment
        verdict = state_dict.get("verdict")
        assessment_doc_id = None
        if verdict:
            db_assessment = await db.assessments.find_one({"session_id": session_doc_id})
            
            # Extract fields
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
            lead_update = {
                "lead_score": lead_score,
            }
            
            if not db_lead:
                from datetime import datetime, timezone
                lead_update["session_id"] = session_doc_id
                lead_update["assessment_id"] = assessment_doc_id
                lead_update["state"] = intake.get("state", "Unknown")
                lead_update["name"] = user_name
                lead_update["status"] = "new"
                lead_update["created_at"] = datetime.now(timezone.utc)
                lead_update["updated_at"] = datetime.now(timezone.utc)
                await db.leads.insert_one(lead_update)
            else:
                if not db_lead.get("state"):
                    lead_update["state"] = intake.get("state", "Unknown")
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
            
    except Exception as e:
        logger.error(f"Failed to sync state to CRM: {e}")
