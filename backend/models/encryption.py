import os
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

# Key should be a base64-encoded 32-byte key. 
# Generate one via `Fernet.generate_key()`
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

fernet = None
if ENCRYPTION_KEY:
    try:
        fernet = Fernet(ENCRYPTION_KEY.encode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to initialize encryption key: {e}")
else:
    logger.warning("No ENCRYPTION_KEY provided. PII fields will not be encrypted.")

def encrypt_data(data: str) -> str:
    """Encrypts string data using Fernet symmetric encryption."""
    if not fernet or not data:
        return data
    return fernet.encrypt(data.encode('utf-8')).decode('utf-8')

def decrypt_data(encrypted_data: str) -> str:
    """Decrypts string data using Fernet symmetric encryption."""
    if not fernet or not encrypted_data:
        return encrypted_data
    try:
        return fernet.decrypt(encrypted_data.encode('utf-8')).decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return encrypted_data
