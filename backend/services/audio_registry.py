import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AudioProvider(ABC):
    @abstractmethod
    async def text_to_speech(self, text: str, lang: str = "hi") -> bytes:
        """Convert text to speech audio bytes"""
        pass

    @abstractmethod
    async def speech_to_text(self, audio_bytes: bytes, lang: str = "hi") -> str:
        """Convert speech audio bytes to text"""
        pass

class AudioRegistry:
    def __init__(self):
        self.providers: Dict[str, AudioProvider] = {}
        self.active_provider: Optional[str] = None
        self.config: Dict[str, Any] = {}

    def register(self, name: str, provider: AudioProvider):
        self.providers[name] = provider

    def set_active(self, name: str, config: Dict[str, Any]):
        if name not in self.providers:
            raise ValueError(f"Unknown audio provider: {name}")
        self.active_provider = name
        self.config = config
        logger.info(f"Switched active audio provider to {name}")

    def get_provider(self) -> AudioProvider:
        if not self.active_provider or self.active_provider not in self.providers:
            raise ValueError("No active audio provider configured")
        return self.providers[self.active_provider]

    async def initialize_from_db(self, db):
        # MVP: Try to load from memory store (in admin_channels), production should use DB
        from api.admin_channels import get_audio_config, audio_config_store
        
        config = await get_audio_config()
        if config.get("configured"):
            provider_name = config.get("provider")
            self.set_active(provider_name, audio_config_store)
            logger.info(f"Loaded audio config from DB: {provider_name}")
            return True
        return False

audio_registry = AudioRegistry()
