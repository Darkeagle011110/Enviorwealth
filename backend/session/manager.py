import json
import redis.asyncio as redis
from typing import Optional, Dict, Any
from config.settings import settings

class SessionManager:
    """
    Redis-backed session manager for ephemeral conversation state.
    TTL is 24 hours (86400 seconds).
    """
    def __init__(self):
        self.redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True
        )
        self.ttl_seconds = 86400

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        data = await self.redis_client.get(f"session:{session_id}")
        if data:
            return json.loads(data)
        return None

    async def save_session(self, session_id: str, state: Dict[str, Any]):
        await self.redis_client.setex(
            f"session:{session_id}",
            self.ttl_seconds,
            json.dumps(state)
        )

    async def clear_session(self, session_id: str):
        await self.redis_client.delete(f"session:{session_id}")
        
    async def check_rate_limit(self, user_ip: str) -> bool:
        """
        Simple token bucket rate limit: Max 50 messages per hour per IP.
        Returns True if allowed, False if limited.
        """
        key = f"ratelimit:{user_ip}"
        current = await self.redis_client.get(key)
        
        if current and int(current) >= 50:
            return False
            
        pipe = self.redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 3600) # 1 hour
        await pipe.execute()
        
        return True

session_manager = SessionManager()
