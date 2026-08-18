"""
WhatsApp Cloud API Webhook

C5 FIX: Removed the blind challenge acceptance. The webhook now requires
WHATSAPP_VERIFY_TOKEN to be set. If it is not configured, the endpoint
returns 503 (not configured) rather than blindly accepting any challenge.
This prevents an attacker from registering our endpoint as their own webhook.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse
import logging
import asyncio
from api.admin_channels import whatsapp_config_store
from orchestrator.graph import orchestrator_app
from services.whatsapp_sender import send_whatsapp_text

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/webhook")
async def verify_webhook(request: Request):
    """
    Meta Graph API Webhook Verification (GET).

    Meta sends hub.mode='subscribe', hub.verify_token, hub.challenge.
    We must echo hub.challenge only if hub.verify_token matches our config.

    C5 FIX: Never accept blindly. Require explicit configuration.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    configured_verify_token = whatsapp_config_store.get("verify_token")

    # Require explicit configuration — never blind-accept
    if not configured_verify_token:
        logger.error(
            "WhatsApp webhook verification attempted but WHATSAPP_VERIFY_TOKEN is not "
            "configured in the Admin panel. Refusing challenge to prevent hijacking. "
            "Configure the token via Admin → Channels."
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "WhatsApp webhook not configured. "
                "Set the verify_token in Admin → Channels before activating the webhook."
            ),
        )

    if not mode or not token or not challenge:
        logger.warning(f"Webhook verification missing parameters: mode={mode}, token_present={bool(token)}")
        raise HTTPException(status_code=400, detail="Missing required webhook verification parameters.")

    if mode == "subscribe" and token == configured_verify_token:
        logger.info("WhatsApp WEBHOOK_VERIFIED successfully.")
        return PlainTextResponse(content=challenge, status_code=200)

    logger.warning(f"WhatsApp webhook verification FAILED — token mismatch. mode={mode}")
    raise HTTPException(status_code=403, detail="Webhook verification failed. Token mismatch.")


@router.post("/webhook")
async def receive_message(request: Request):
    """
    Receives incoming WhatsApp messages from the Meta Graph API.
    Always returns 200 to Meta immediately (required by their protocol).
    Processing is logged — full orchestrator integration is Phase 3.
    """
    try:
        body = await request.json()
    except Exception:
        logger.error("WhatsApp webhook received non-JSON body.")
        return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)

    logger.debug(f"Incoming WhatsApp webhook payload keys: {list(body.keys())}")

    try:
        if "entry" in body:
            for entry in body.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})

                    if "messages" in value:
                        for message in value["messages"]:
                            sender_phone = message.get("from", "unknown")
                            msg_type = message.get("type", "unknown")

                            if msg_type == "text":
                                text_body = message.get("text", {}).get("body", "")
                                logger.info(f"WhatsApp text from {sender_phone}: {text_body[:80]}")
                                
                                # Send to LangGraph in the background to not block the webhook 200 response
                                asyncio.create_task(process_whatsapp_message(sender_phone, text_body))

                            elif msg_type == "audio":
                                audio_id = message.get("audio", {}).get("id")
                                logger.info(f"WhatsApp audio from {sender_phone}, media_id={audio_id}")
                                # TODO Phase 3: download → ASR (Bhashini/Whisper) → orchestrator → TTS → reply
                                asyncio.create_task(send_whatsapp_text(sender_phone, "Audio messages are not fully supported yet in this MVP."))

                            else:
                                logger.info(f"WhatsApp {msg_type} message from {sender_phone} — not yet handled.")

                    if "statuses" in value:
                        for status_update in value["statuses"]:
                            logger.debug(f"WhatsApp status update: {status_update.get('status')} for {status_update.get('id')}")

    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook payload: {e}", exc_info=True)
        # Still return 200 — Meta will retry if we return non-200

    # Meta requires a 200 response within 20s or it will retry
    return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)

async def process_whatsapp_message(sender_phone: str, text: str):
    try:
        logger.info(f"Invoking orchestrator for {sender_phone}")
        session_id = f"wa_{sender_phone}"
        initial_state = {
            "session_id": session_id,
            "user_id": sender_phone,
            "messages": [{"role": "user", "content": text}],
            "turn_count": 1,
            "intake_data": {},
            "missing_fields": [],
            "rag_citations": [],
            "web_search_results": [],
            "rag_sufficient": True,
            "conversation_summary": "",
            "route_to": None,
            "ui_state": {},
            "screening_started": False,
        }
        config = {"configurable": {"thread_id": session_id}}

        res = await orchestrator_app.ainvoke(initial_state, config=config)

        # Extract the last assistant message
        final_messages = res.get("messages", [])
        reply_text = ""
        for msg in reversed(final_messages):
            if msg.get("role") == "assistant":
                reply_text = msg.get("content", "")
                break

        if reply_text:
            await send_whatsapp_text(sender_phone, reply_text)
        else:
            logger.warning(f"No assistant reply found for {sender_phone}")
    except Exception as e:
        logger.error(f"Error in process_whatsapp_message: {e}")
        await send_whatsapp_text(sender_phone, "Sorry, I encountered an error processing your request.")

