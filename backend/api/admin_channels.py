from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# In-memory storage for MVP (should be in DB for production)
whatsapp_config_store = {}
audio_config_store = {}
multilingual_config_store = {
    "enabled": False,
    "audio_provider": "bhashini",
    "supported_languages": ["hi", "gu", "mr"]
}

class WhatsAppConfig(BaseModel):
    phone_number_id: str
    access_token: str
    verify_token: str

class AudioConfig(BaseModel):
    provider: str
    api_key: Optional[str] = None
    user_id: Optional[str] = None
    pipeline_id: Optional[str] = None

@router.post("/whatsapp")
async def save_whatsapp_config(config: WhatsAppConfig):
    # In production, encrypt tokens before saving to DB
    whatsapp_config_store['phone_number_id'] = config.phone_number_id
    whatsapp_config_store['access_token'] = config.access_token
    whatsapp_config_store['verify_token'] = config.verify_token
    return {"message": "WhatsApp configuration saved successfully"}

@router.get("/whatsapp")
async def get_whatsapp_config():
    if not whatsapp_config_store:
        return {"configured": False}
    return {
        "configured": True,
        "phone_number_id": whatsapp_config_store.get("phone_number_id")
    }

@router.post("/audio")
async def save_audio_config(config: AudioConfig):
    # Depending on provider, validate fields
    if config.provider == "bhashini":
        if not all([config.api_key, config.user_id, config.pipeline_id]):
            raise HTTPException(status_code=400, detail="Missing Bhashini credentials")
    elif config.provider in ["gemini", "whisper"]:
        if not config.api_key:
            raise HTTPException(status_code=400, detail=f"Missing API key for {config.provider}")
    else:
        raise HTTPException(status_code=400, detail="Unknown audio provider")
    
    # Store configuration
    audio_config_store['provider'] = config.provider
    audio_config_store['api_key'] = config.api_key
    audio_config_store['user_id'] = config.user_id
    audio_config_store['pipeline_id'] = config.pipeline_id
    
    return {"message": f"{config.provider} audio configuration saved successfully"}

@router.get("/audio")
async def get_audio_config():
    if not audio_config_store:
        return {"configured": False}
    return {
        "configured": True,
        "provider": audio_config_store.get("provider")
    }

class MultilingualConfig(BaseModel):
    enabled: bool
    audio_provider: str
    supported_languages: list[str] = ["hi", "gu", "mr"]

@router.post("/multilingual")
async def save_multilingual_config(config: MultilingualConfig):
    multilingual_config_store['enabled'] = config.enabled
    multilingual_config_store['audio_provider'] = config.audio_provider
    multilingual_config_store['supported_languages'] = config.supported_languages
    return {"message": "Multilingual configuration saved successfully"}

@router.get("/multilingual")
async def get_multilingual_config():
    return multilingual_config_store
