from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from models.mongodb import get_db

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
async def register_user(request: UserRegisterRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    if not request.mobile and not request.email:
        raise HTTPException(status_code=400, detail="Must provide either mobile or email")

    # Basic upsert logic on email or mobile (for a real app, this would be more robust)
    existing_user = None
    if request.email:
        existing_user = await db.leads.find_one({"email": request.email})
    elif request.mobile:
        existing_user = await db.leads.find_one({"mobile": request.mobile})

    if existing_user:
        user_id = str(existing_user.get("id", existing_user.get("_id")))
        logger.info(f"User already registered: {user_id}")
        return UserRegisterResponse(user_id=user_id, status="existing")

    from datetime import datetime, timezone
    new_lead = {
        "id": str(uuid.uuid4()),
        "name": request.name,
        "mobile": request.mobile,
        "email": request.email,
        "consent_given": True,
        "status": "registered",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    try:
        res = await db.leads.insert_one(new_lead)
        user_id = new_lead["id"]
        logger.info(f"New user registered: {user_id}")
        return UserRegisterResponse(user_id=user_id, status="created")
    except Exception as e:
        logger.error(f"Failed to register user: {e}")
        raise HTTPException(status_code=500, detail="Failed to register user")
