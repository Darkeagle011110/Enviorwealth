import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from models.mongodb import get_database

class SessionManager:
    """
    MongoDB-backed session manager for ephemeral conversation state.
    Replaces Redis. TTL is handled by MongoDB TTL indexes (24 hours).
    """
    def __init__(self):
        self.ttl_seconds = 86400

    def _now(self):
        return datetime.now(timezone.utc)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        db = get_database()
        doc = await db.sessions.find_one({"_id": session_id})
        if doc:
            return doc.get("state")
        return None

    async def save_session(self, session_id: str, state: Dict[str, Any]):
        db = get_database()
        expires_at = self._now() + timedelta(seconds=self.ttl_seconds)
        doc = {
            "_id": session_id,
            "state": state,
            "expires_at": expires_at
        }
        await db.sessions.replace_one({"_id": session_id}, doc, upsert=True)

    async def clear_session(self, session_id: str):
        db = get_database()
        await db.sessions.delete_one({"_id": session_id})
        
    async def check_rate_limit(self, user_ip: str) -> bool:
        """
        Simple rate limit: Max 50 messages per hour per IP.
        Uses atomic $inc and MongoDB TTL index on rate_limits collection.
        """
        db = get_database()
        expires_at = self._now() + timedelta(hours=1)
        
        doc = await db.rate_limits.find_one_and_update(
            {"_id": user_ip},
            {
                "$inc": {"count": 1},
                "$setOnInsert": {"expires_at": expires_at}
            },
            upsert=True,
            return_document=True
        )
        
        if doc and doc.get("count", 0) > 50:
            return False
            
        return True

session_manager = SessionManager()
