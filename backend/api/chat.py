"""
Chat API — POST /api/v1/chat

Entry point for the conversational interface. Routes through the LangGraph
orchestrator, manages MongoDB session state, and returns structured responses.
"""
import logging
import uuid
import json
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from orchestrator.graph import orchestrator_app
from session.manager import session_manager
from utils.crm_sync import sync_state_to_crm
from memo.template_engine import MemoTemplateEngine
from api.client_auth import get_current_client_user
from models.schemas import ClientUserDoc
from models.mongodb import get_db
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    ui_state: Dict[str, Any]
    verdict: Optional[Dict[str, Any]] = None


def _sanitize_state_for_session(state: dict) -> dict:
    """
    Convert all Pydantic objects in the graph state to JSON-safe dicts.
    MongoDB uses BSON which handles dicts, but Pydantic models need converting.
    """
    sanitized = {}
    for key, value in state.items():
        if hasattr(value, "model_dump"):
            sanitized[key] = value.model_dump(mode="json")
        elif hasattr(value, "dict"):
            sanitized[key] = json.loads(value.json())
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_state_for_session(value)
        elif isinstance(value, list):
            sanitized[key] = [
                (item.model_dump(mode="json") if hasattr(item, "model_dump")
                 else (json.loads(item.json()) if hasattr(item, "dict") else item))
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, req: Request, current_user: ClientUserDoc = Depends(get_current_client_user)):
    user_ip = req.client.host if req.client else "unknown"

    if not await session_manager.check_rate_limit(user_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again in a few minutes.")

    session_id = request.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        initial_state: Dict[str, Any] = {
            "session_id": session_id,
            "user_id": request.user_id,
            "messages": [],
            "turn_count": 0,
            "intake_data": {},
            "missing_fields": [],
            "rag_citations": [],
            "agentic_loop_count": 0,
            "ui_state": {},
            "screening_started": False,
        }
    else:
        initial_state = await session_manager.get_session(session_id)
        if not initial_state:
            initial_state = {
                "session_id": session_id,
                "user_id": request.user_id,
                "messages": [],
                "turn_count": 0,
                "intake_data": {},
                "missing_fields": [],
                "rag_citations": [],
                "agentic_loop_count": 0,
                "ui_state": {},
                "screening_started": False,
            }

    if current_user:
        initial_state["user_id"] = str(current_user.id)

    if "ui_state" in initial_state and isinstance(initial_state["ui_state"], dict):
        initial_state["ui_state"].pop("action", None)

    initial_state["messages"].append({"role": "user", "content": request.message})
    initial_state["turn_count"] = initial_state.get("turn_count", 0) + 1
    turn_thread_id = f"{session_id}__turn_{initial_state['turn_count']}"

    try:
        final_state = await orchestrator_app.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": turn_thread_id}},
        )

    except Exception as e:
        logger.error(f"Graph execution failed for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred processing your request.")

    try:
        safe_state = _sanitize_state_for_session(dict(final_state))
        await session_manager.save_session(session_id, safe_state)
        asyncio.create_task(sync_state_to_crm(session_id, safe_state, current_user.id, current_user.full_name))
    except Exception as e:
        logger.warning(f"Session save failed for {session_id}: {e}")

    reply = ""
    messages = final_state.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            reply = msg["content"]
            break

    response = ChatResponse(
        session_id=session_id,
        reply=reply,
        ui_state=final_state.get("ui_state", {}),
    )

    verdict = final_state.get("verdict")
    if verdict:
        try:
            explanation = reply
            memo_data = MemoTemplateEngine.build_memo(verdict, explanation)
            response.verdict = memo_data
        except Exception as e:
            logger.warning(f"Memo build failed: {e}")

    return response

class SessionHistoryResponse(BaseModel):
    session_id: str
    created_at: str
    preview: str

@router.get("/user/sessions", response_model=List[SessionHistoryResponse])
async def get_user_sessions(current_user: ClientUserDoc = Depends(get_current_client_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    """Fetch all chat sessions for the logged in user."""
    sessions_cursor = db.assessment_sessions.find({"user_id": current_user.id}).sort("created_at", -1)
    sessions = await sessions_cursor.to_list(length=None)
    
    result = []
    for s in sessions:
        preview = "New Assessment"
        intake_data = s.get("intake_data", {})
        if intake_data and isinstance(intake_data, dict):
             if "area_ha" in intake_data:
                 preview = f"Assessment - {intake_data['area_ha']} ha"
        
        created_at = s.get("created_at")
        
        result.append(SessionHistoryResponse(
            session_id=s.get("session_token", ""),
            created_at=created_at.isoformat() if created_at else "",
            preview=preview
        ))
    return result
