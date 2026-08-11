"""
Chat API — POST /api/v1/chat

Entry point for the conversational interface. Routes through the LangGraph
orchestrator, manages Redis session state, and returns structured responses.

C7 FIX: Added state sanitization before Redis serialization.
The graph state can contain Pydantic objects (Verdict, Tier1Intake) which
json.dumps() cannot serialize. These are now converted to dicts before saving.
"""
import logging
import uuid
import json
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from orchestrator.graph import orchestrator_app
from session.manager import session_manager
from utils.crm_sync import sync_state_to_crm
from memo.template_engine import MemoTemplateEngine
from api.client_auth import get_current_client_user
from models.orm_models import ClientUser, AssessmentSession
from models.database import get_db
from sqlalchemy.orm import Session

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
    C7 FIX: Convert all Pydantic objects in the graph state to JSON-safe dicts.
    Redis session uses json.dumps() — Pydantic models are not natively JSON-serializable.
    """
    sanitized = {}
    for key, value in state.items():
        if hasattr(value, "model_dump"):
            # Pydantic v2
            sanitized[key] = value.model_dump(mode="json")
        elif hasattr(value, "dict"):
            # Pydantic v1
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
async def chat_endpoint(request: ChatRequest, req: Request, current_user: ClientUser = Depends(get_current_client_user)):
    """
    Main chat entry point. Invokes the LangGraph orchestrator and
    returns the assistant reply + structured UI state.
    """
    user_ip = req.client.host if req.client else "unknown"

    # 1. Rate limiting
    if not await session_manager.check_rate_limit(user_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again in a few minutes.")

    # 2. Session management
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

    # Clear transient UI actions from previous turns to prevent recurring popups
    if "ui_state" in initial_state and isinstance(initial_state["ui_state"], dict):
        initial_state["ui_state"].pop("action", None)

    # Append user message
    initial_state["messages"].append({"role": "user", "content": request.message})
    initial_state["turn_count"] = initial_state.get("turn_count", 0) + 1

    # CRITICAL FIX (Bug 2): Use a unique thread_id per turn so LangGraph's MemorySaver
    # never serves a stale checkpoint that lacks the current intake_data.
    # Redis is the single source of truth — the full restored state is always passed
    # directly as input, overriding anything LangGraph may have cached.
    turn_thread_id = f"{session_id}__turn_{initial_state['turn_count']}"

    # 3. Invoke LangGraph orchestrator
    try:
        final_state = await orchestrator_app.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": turn_thread_id}},
        )

    except Exception as e:
        logger.error(f"Graph execution failed for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred processing your request.")

    # 4. Save session (C7 FIX: sanitize Pydantic objects before JSON serialization)
    try:
        safe_state = _sanitize_state_for_session(dict(final_state))
        await session_manager.save_session(session_id, safe_state)
        # Background sync to postgres CRM
        import asyncio
        asyncio.create_task(asyncio.to_thread(sync_state_to_crm, session_id, safe_state, current_user.id, current_user.full_name))
    except Exception as e:
        logger.warning(f"Session save failed for {session_id}: {e}")
        # Non-fatal — response is still returned

    # 5. Extract reply from the last assistant message
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

    # 6. If a verdict is available, build the structured memo for the UI
    verdict = final_state.get("verdict")
    if verdict:
        try:
            # Find the explanation from the explain_node in message history
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
async def get_user_sessions(current_user: ClientUser = Depends(get_current_client_user), db: Session = Depends(get_db)):
    """Fetch all chat sessions for the logged in user."""
    # Since chats are primarily in Redis or synced to CRM (AssessmentSession),
    # we can fetch from postgres AssessmentSession where user_id matches
    sessions = db.query(AssessmentSession).filter(AssessmentSession.user_id == current_user.id).order_by(AssessmentSession.created_at.desc()).all()
    
    result = []
    for s in sessions:
        # Create a basic preview from intake data or fallback
        preview = "New Assessment"
        if s.intake_data and isinstance(s.intake_data, dict):
             if "area_ha" in s.intake_data:
                 preview = f"Assessment - {s.intake_data['area_ha']} ha"
        
        result.append(SessionHistoryResponse(
            session_id=s.session_token,
            created_at=s.created_at.isoformat() if s.created_at else "",
            preview=preview
        ))
    return result

