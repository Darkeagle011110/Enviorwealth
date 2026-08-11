from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
import logging
from models.database import get_db
from models.orm_models import Lead
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()

class UserRegisterRequest(BaseModel):
    name: str
    mobile: Optional[str] = None
    email: Optional[str] = None

class UserRegisterResponse(BaseModel):
    user_id: str
    status: str

@router.post("/user/register", response_model=UserRegisterResponse)
async def register_user(request: UserRegisterRequest, db: Session = Depends(get_db)):
    if not request.mobile and not request.email:
        raise HTTPException(status_code=400, detail="Must provide either mobile or email")

    # Basic upsert logic on email or mobile (for a real app, this would be more robust)
    existing_user = None
    if request.email:
        existing_user = db.query(Lead).filter(Lead.email == request.email).first()
    elif request.mobile:
        existing_user = db.query(Lead).filter(Lead.mobile == request.mobile).first()

    if existing_user:
        logger.info(f"User already registered: {existing_user.id}")
        return UserRegisterResponse(user_id=str(existing_user.id), status="existing")

    new_lead = Lead(
        name=request.name,
        mobile=request.mobile,
        email=request.email,
        consent_given=True,
        status="registered"
    )
    
    try:
        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)
        logger.info(f"New user registered: {new_lead.id}")
        return UserRegisterResponse(user_id=str(new_lead.id), status="created")
    except Exception as e:
        logger.error(f"Failed to register user: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to register user")
