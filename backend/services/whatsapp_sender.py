import logging
import httpx
from typing import List
from api.admin_channels import whatsapp_config_store

logger = logging.getLogger(__name__)

async def send_whatsapp_text(recipient_phone: str, text: str) -> bool:
    """
    Sends a text message to a WhatsApp user via the Meta Cloud API.
    Handles message chunking if the text is too long.
    """
    token = whatsapp_config_store.get("access_token")
    phone_id = whatsapp_config_store.get("phone_number_id")

    if not token or not phone_id:
        logger.error("WhatsApp Cloud API not configured. Cannot send message.")
        return False

    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # WhatsApp has a limit of 4096 characters per text message.
    # We chunk at 4000 to be safe.
    chunks = chunk_text(text, limit=4000)
    success = True
    
    async with httpx.AsyncClient() as client:
        for chunk in chunks:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient_phone,
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": chunk
                }
            }
            try:
                res = await client.post(url, headers=headers, json=payload)
                res.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to send WhatsApp message chunk to {recipient_phone}: {e}")
                success = False

    return success

def chunk_text(text: str, limit: int = 4000) -> List[str]:
    """
    Splits text into chunks of maximum size `limit`, trying to break on newlines or spaces.
    """
    if len(text) <= limit:
        return [text]

    chunks = []
    while len(text) > limit:
        # Find the last newline or space within the limit
        split_idx = text.rfind('\n', 0, limit)
        if split_idx == -1:
            split_idx = text.rfind(' ', 0, limit)
            
        if split_idx == -1:
            # If no good breaking point, just hard split
            split_idx = limit
            
        chunks.append(text[:split_idx].strip())
        text = text[split_idx:].strip()

    if text:
        chunks.append(text)
        
    return chunks
