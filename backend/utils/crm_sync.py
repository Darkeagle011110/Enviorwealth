import logging
import uuid
from sqlalchemy.orm import Session
from models.database import SessionLocal
from models.orm_models import AssessmentSession, Assessment, Lead
from engine.schemas import VerdictCategory

logger = logging.getLogger(__name__)

def sync_state_to_crm(session_id: str, state_dict: dict, user_id=None, user_name="Anonymous User"):
    """
    Syncs the current conversation state into the Postgres CRM tables.
    """
    db = SessionLocal()
    try:
        # 1. Update or Create AssessmentSession
        db_session = db.query(AssessmentSession).filter(AssessmentSession.session_token == session_id).first()
        if not db_session:
            db_session = AssessmentSession(session_token=session_id, user_id=user_id)
            db.add(db_session)
        
        db_session.intake_data = state_dict.get("intake_data", {})
        db_session.tier = 1
        db.commit()
        db.refresh(db_session)
        
        # 2. If verdict exists, save Assessment
        verdict = state_dict.get("verdict")
        db_assessment = None
        if verdict:
            # check if it already exists
            db_assessment = db.query(Assessment).filter(Assessment.session_id == db_session.id).first()
            if not db_assessment:
                db_assessment = Assessment(session_id=db_session.id)
                db.add(db_assessment)
            
            # verdict could be a dict if it was sanitized, or a Pydantic model
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
                
            db_assessment.verdict = v_cat or "UNKNOWN"
            db_assessment.confidence = confidence
            db_assessment.knockout_gate = knockout_gate
            db_assessment.flags = flags
            db.commit()
            db.refresh(db_assessment)
        
        # 3. If lead_score exists, save Lead
        lead_score = state_dict.get("lead_score")
        if lead_score and db_assessment:
            db_lead = db.query(Lead).filter(Lead.session_id == db_session.id).first()
            if not db_lead:
                db_lead = Lead(session_id=db_session.id, assessment_id=db_assessment.id)
                db.add(db_lead)
            
            db_lead.lead_score = lead_score
            # Extract basic info from intake_data if available
            intake = db_session.intake_data
            if not db_lead.state:
                db_lead.state = intake.get("state", "Unknown")
            if not db_lead.name:
                db_lead.name = user_name
            
            db_lead.status = db_lead.status or "new"
            db.commit()
            
    except Exception as e:
        logger.error(f"Failed to sync state to CRM: {e}")
        db.rollback()
    finally:
        db.close()
