import httpx
import logging
from .audio_registry import AudioProvider, audio_registry

logger = logging.getLogger(__name__)

class BhashiniProvider(AudioProvider):
    async def text_to_speech(self, text: str, lang: str = "hi") -> bytes:
        config = audio_registry.config
        if not config.get("api_key") or not config.get("user_id") or not config.get("pipeline_id"):
            raise ValueError("Bhashini credentials not fully configured")
        
        logger.info(f"Bhashini TTS requested for lang {lang}: {text[:20]}...")
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": config.get("api_key"),
                "Content-Type": "application/json"
            }
            # Note: This is an illustrative payload structure for Bhashini. 
            # In production, you would first call the compute endpoint to get the service ID.
            payload = {
                "pipelineTasks": [{"taskType": "tts", "config": {"language": {"sourceLanguage": lang}}}],
                "inputData": {"input": [{"source": text}]}
            }
            response = await client.post("https://dhruva-api.bhashini.gov.in/services/inference/pipeline", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            # Extract audio bytes from response (assuming base64 encoded audioContent)
            import base64
            audio_content = data.get("pipelineResponse", [{}])[0].get("audio", [{}])[0].get("audioContent", "")
            if not audio_content:
                raise ValueError("No audio content in Bhashini response")
            return base64.b64decode(audio_content)

    async def speech_to_text(self, audio_bytes: bytes, lang: str = "hi") -> str:
        config = audio_registry.config
        if not config.get("api_key") or not config.get("user_id") or not config.get("pipeline_id"):
            raise ValueError("Bhashini credentials not fully configured")
        
        logger.info(f"Bhashini ASR requested for {len(audio_bytes)} bytes")
        import base64
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": config.get("api_key"),
                "Content-Type": "application/json"
            }
            payload = {
                "pipelineTasks": [{"taskType": "asr", "config": {"language": {"sourceLanguage": lang}}}],
                "inputData": {"audio": [{"audioContent": audio_b64}]}
            }
            response = await client.post("https://dhruva-api.bhashini.gov.in/services/inference/pipeline", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            # Extract text
            text_content = data.get("pipelineResponse", [{}])[0].get("output", [{}])[0].get("source", "")
            return text_content

class GeminiAudioProvider(AudioProvider):
    async def text_to_speech(self, text: str, lang: str = "hi") -> bytes:
        config = audio_registry.config
        logger.info(f"Gemini TTS requested for lang {lang}")
        return b"MOCK_WAV_BYTES_FROM_GEMINI"

    async def speech_to_text(self, audio_bytes: bytes, lang: str = "hi") -> str:
        config = audio_registry.config
        logger.info(f"Gemini ASR requested")
        return "Mock gemini translation"

class WhisperProvider(AudioProvider):
    async def text_to_speech(self, text: str, lang: str = "hi") -> bytes:
        config = audio_registry.config
        logger.info(f"Whisper TTS requested for lang {lang}")
        # OpenAI TTS API
        return b"MOCK_WAV_BYTES_FROM_WHISPER"

    async def speech_to_text(self, audio_bytes: bytes, lang: str = "hi") -> str:
        config = audio_registry.config
        logger.info(f"Whisper ASR requested")
        # OpenAI Whisper API
        return "Mock whisper translation"

# Register providers
audio_registry.register("bhashini", BhashiniProvider())
audio_registry.register("gemini", GeminiAudioProvider())
audio_registry.register("whisper", WhisperProvider())
