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
from api.client_auth import get_optional_client_user, get_current_client_user
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
async def chat_endpoint(request: ChatRequest, req: Request, current_user: Optional[ClientUserDoc] = Depends(get_optional_client_user)):
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
        
        user_id = str(current_user.id) if current_user else "anonymous"
        user_name = current_user.full_name if current_user else "Anonymous"
        asyncio.create_task(sync_state_to_crm(session_id, safe_state, user_id, user_name))
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


class SessionDetailResponse(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]
    intake_data: Dict[str, Any]
    verdict: Optional[Dict[str, Any]] = None


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    current_user: ClientUserDoc = Depends(get_current_client_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Fetch the full message history and state for a past session.
    Used by the frontend Sidebar to restore chat messages when a user
    clicks on a previous assessment in the history list.
    """
    # Verify the session belongs to this user
    db_session = await db.assessment_sessions.find_one({
        "session_token": session_id,
        "user_id": current_user.id,
    })
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load conversation state from the sessions collection (ephemeral, 24hr TTL)
    state = await session_manager.get_session(session_id)

    messages: List[Dict[str, Any]] = []
    intake_data: Dict[str, Any] = {}
    verdict = None

    if state:
        raw_messages = state.get("messages", [])
        # Filter out internal JSON payloads (eligibility_form submissions)
        for msg in raw_messages:
            content = msg.get("content", "")
            if msg.get("role") == "user" and '"eligibility_form"' in content:
                # Replace raw JSON with a user-friendly placeholder
                messages.append({
                    "role": "user",
                    "content": "📋 Submitted Eligibility Assessment Form",
                    "timestamp": msg.get("timestamp"),
                })
            else:
                messages.append(msg)
        intake_data = state.get("intake_data", {})
        raw_verdict = state.get("verdict")
        if raw_verdict:
            if hasattr(raw_verdict, "model_dump"):
                verdict = raw_verdict.model_dump(mode="json")
            elif isinstance(raw_verdict, dict):
                verdict = raw_verdict
    else:
        # Session TTL has expired — load what we can from permanent storage
        intake_data = db_session.get("intake_data", {})
        # Try to get verdict from assessments collection
        assessment = await db.assessments.find_one({"session_id": str(db_session.get("_id"))})
        if assessment:
            verdict = {
                "verdict": assessment.get("verdict"),
                "confidence": assessment.get("confidence"),
                "flags": assessment.get("flags", []),
            }
        # Notify user that message history has expired
        messages = [{
            "role": "assistant",
            "content": (
                "📂 This is a past assessment. The detailed conversation history has expired "
                "(sessions are kept for 24 hours), but your eligibility result is shown above. "
                "Start a new assessment to chat again."
            ),
        }]

    return SessionDetailResponse(
        session_id=session_id,
        messages=messages,
        intake_data=intake_data,
        verdict=verdict,
    )

