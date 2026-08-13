from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from pydantic import BaseModel
from models.mongodb import get_db
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
async def get_leads(status: Optional[str] = None, db: AsyncIOMotorDatabase = Depends(get_db)):
    query = {}
    if status:
        query["status"] = status
    
    cursor = db.leads.find(query).sort("created_at", -1)
    db_leads = await cursor.to_list(length=None)
    results = []
    
    for lead in db_leads:
        # Fetch related assessment and session to populate fields
        assessment_id = lead.get("assessment_id")
        assessment = None
        if assessment_id:
            assessment = await db.assessments.find_one({"$or": [{"id": assessment_id}, {"_id": assessment_id}]})
            
        session_id = lead.get("session_id")
        session = None
        if session_id:
            session = await db.assessment_sessions.find_one({"$or": [{"id": session_id}, {"_id": session_id}]})
        
        intake = session.get("intake_data", {}) if session else {}
        area = intake.get("area_ha", 0.0)
        location = lead.get("state") or "Unknown"
        verdict = assessment.get("verdict", "Unknown") if assessment else "Unknown"
        intent = "Carbon" # Hardcoded for now unless we capture intent elsewhere
        
        created_at = lead.get("created_at")
        
        results.append(LeadSummary(
            id=str(lead.get("id", lead.get("_id"))),
            session_id=str(session.get("session_token", "")) if session else "",
            name=lead.get("name") or "Anonymous",
            location=location,
            area=float(area),
            verdict=verdict,
            intent=intent,
            status=lead.get("status") or "new",
            created_at=created_at.isoformat() if created_at else ""
        ))
    return results

@router.get("/leads/{lead_id}")
async def get_lead_details(lead_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    lead = await db.leads.find_one({"$or": [{"id": lead_id}, {"_id": lead_id}]})
    
    # fallback to ObjectId if needed
    if not lead:
        try:
            from bson import ObjectId
            lead = await db.leads.find_one({"_id": ObjectId(lead_id)})
        except Exception:
            pass
            
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    assessment = None
    if lead.get("assessment_id"):
        assessment = await db.assessments.find_one({"$or": [{"id": lead.get("assessment_id")}, {"_id": lead.get("assessment_id")}]})
        
    session = None
    if lead.get("session_id"):
        session = await db.assessment_sessions.find_one({"$or": [{"id": lead.get("session_id")}, {"_id": lead.get("session_id")}]})
    
    from session.manager import session_manager
    redis_state = {}
    if session and session.get("session_token"):
        try:
            redis_state = await session_manager.get_session(session["session_token"])
        except Exception:
            pass
            
    messages = redis_state.get("messages", []) if redis_state else []
    created_at = lead.get("created_at")
        
    return {
        "id": str(lead.get("id", lead.get("_id"))),
        "personal_info": {
            "name": lead.get("name"),
            "mobile": lead.get("mobile"),
            "email": lead.get("email"),
            "preferred_contact": lead.get("preferred_contact")
        },
        "land_info": session.get("intake_data", {}) if session else {},
        "verdict": assessment.get("verdict") if assessment else None,
        "confidence": assessment.get("confidence") if assessment else None,
        "flags": assessment.get("flags", []) if assessment else [],
        "lead_score": lead.get("lead_score"),
        "status": lead.get("status"),
        "notes": lead.get("notes"),
        "created_at": created_at.isoformat() if created_at else None,
        "conversation": messages
    }

@router.post("/leads/{lead_id}/status")
async def update_lead_status(lead_id: str, payload: dict, db: AsyncIOMotorDatabase = Depends(get_db)):
    from bson import ObjectId
    query = {"$or": [{"id": lead_id}, {"_id": lead_id}]}
    
    try:
        query["$or"].append({"_id": ObjectId(lead_id)})
    except Exception:
        pass
        
    lead = await db.leads.find_one(query)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    new_status = payload.get("status")
    notes = payload.get("notes")
    
    update_data = {}
    if new_status:
        update_data["status"] = new_status
    if notes is not None:
        update_data["notes"] = notes
        
    if update_data:
        await db.leads.update_one({"_id": lead["_id"]}, {"$set": update_data})
        
    return {"status": "success", "new_status": new_status or lead.get("status")}
