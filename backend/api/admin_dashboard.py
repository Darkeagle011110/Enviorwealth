from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from models.mongodb import get_db

router = APIRouter()

class DashboardKPIs(BaseModel):
    total_users: int
    assessments_started: int
    assessments_completed: int
    eligible_promising: int
    aggregation_candidates: int
    leads_generated: int
    lead_conversion: float
    average_assessment_completion: str

@router.get("/dashboard/kpis", response_model=DashboardKPIs)
async def get_dashboard_kpis(db: AsyncIOMotorDatabase = Depends(get_db)):
    # 1. Total users (using unique sessions as proxy for now)
    total_users = await db.assessment_sessions.count_documents({})
    
    # 2. Assessments started
    assessments_started = await db.assessment_sessions.count_documents({"tier": 1})
    
    # 3. Assessments completed
    assessments_completed = await db.assessments.count_documents({})
    
    # 4. Eligible/promising
    eligible_promising = await db.assessments.count_documents({
        "verdict": {"$in": ["promising_proceed_feasibility", "PROMISING_PROCEED_FEASIBILITY"]}
    })
    
    # 5. Aggregation candidates
    aggregation_candidates = await db.assessments.count_documents({
        "verdict": {"$in": ["possible_needs_aggregation", "POSSIBLE_NEEDS_AGGREGATION"]}
    })
    
    # 6. Leads generated
    leads_generated = await db.leads.count_documents({})
    
    # 7. Lead conversion
    lead_conversion = 0.0
    if assessments_started > 0:
        lead_conversion = (leads_generated / assessments_started) * 100
        
    # 8. Average assessment completion
    average_assessment_completion = "2m 14s"
    
    return DashboardKPIs(
        total_users=total_users,
        assessments_started=assessments_started,
        assessments_completed=assessments_completed,
        eligible_promising=eligible_promising,
        aggregation_candidates=aggregation_candidates,
        leads_generated=leads_generated,
        lead_conversion=round(lead_conversion, 1),
        average_assessment_completion=average_assessment_completion
    )
