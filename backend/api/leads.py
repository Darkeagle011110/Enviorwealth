from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel
from models.database import get_db
from models.orm_models import Lead, AssessmentSession, Assessment
import json

router = APIRouter()

class LeadSummary(BaseModel):
    id: str
    session_id: str
    name: str
    location: str
    area: float
    verdict: str
    intent: str
    status: str
    created_at: str

@router.get("/leads", response_model=List[LeadSummary])
async def get_leads(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Lead).order_by(desc(Lead.created_at))
    if status:
        query = query.filter(Lead.status == status)
    
    db_leads = query.all()
    results = []
    
    for lead in db_leads:
        # Fetch related assessment and session to populate fields
        assessment = db.query(Assessment).filter(Assessment.id == lead.assessment_id).first()
        session = db.query(AssessmentSession).filter(AssessmentSession.id == lead.session_id).first()
        
        intake = session.intake_data if session and session.intake_data else {}
        area = intake.get("area_ha", 0.0)
        location = lead.state or "Unknown"
        verdict = assessment.verdict if assessment else "Unknown"
        intent = "Carbon" # Hardcoded for now unless we capture intent elsewhere
        
        results.append(LeadSummary(
            id=str(lead.id),
            session_id=str(session.session_token) if session else "",
            name=lead.name or "Anonymous",
            location=location,
            area=float(area),
            verdict=verdict,
            intent=intent,
            status=lead.status or "new",
            created_at=lead.created_at.isoformat() if lead.created_at else ""
        ))
    return results

@router.get("/leads/{lead_id}")
async def get_lead_details(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    assessment = db.query(Assessment).filter(Assessment.id == lead.assessment_id).first()
    session = db.query(AssessmentSession).filter(AssessmentSession.id == lead.session_id).first()
    
    # We might need to fetch the full conversation from Redis if it's not fully in postgres.
    # But for now, we'll return what we have in postgres.
    # Actually, we should fetch from Redis using session_manager.
    from session.manager import session_manager
    redis_state = {}
    if session:
        try:
            import asyncio
            redis_state = await session_manager.get_session(session.session_token)
        except Exception:
            pass
            
    messages = redis_state.get("messages", []) if redis_state else []
        
    return {
        "id": str(lead.id),
        "personal_info": {
            "name": lead.name,
            "mobile": lead.mobile,
            "email": lead.email,
            "preferred_contact": lead.preferred_contact
        },
        "land_info": session.intake_data if session else {},
        "verdict": assessment.verdict if assessment else None,
        "confidence": assessment.confidence if assessment else None,
        "flags": assessment.flags if assessment else [],
        "lead_score": lead.lead_score,
        "status": lead.status,
        "notes": lead.notes,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "conversation": messages
    }

@router.post("/leads/{lead_id}/status")
async def update_lead_status(lead_id: str, payload: dict, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    new_status = payload.get("status")
    notes = payload.get("notes")
    
    if new_status:
        lead.status = new_status
    if notes is not None:
        lead.notes = notes
        
    db.commit()
    return {"status": "success", "new_status": lead.status}
