"""
Admin Authentication — JWT-based.

C2 FIX: Removed hardcoded password hash from source code.
All secrets MUST be supplied via environment variables.
The app will raise a clear error at startup if critical secrets are missing or
left at their insecure defaults.

To generate a bcrypt hash for your admin password, run:
    python -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt(12)).decode())"

To generate a secure JWT secret, run:
    python -c "import secrets; print(secrets.token_hex(32))"
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel
import os
from config.settings import settings

logger = logging.getLogger(__name__)

# ── Secret validation ─────────────────────────────────────────────────────────
_INSECURE_DEFAULTS = {
    "super-secret-default-key-change-me",
    "change-me-before-production",
    "",
}

SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_expire_minutes

ADMIN_USERNAME = settings.admin_username
# No default hash — must be explicitly set in .env
ADMIN_PASSWORD_HASH = settings.admin_password_hash

def _validate_auth_config():
    """
    Called at startup. Raises RuntimeError if auth is misconfigured.
    Logs a stern warning in development; raises in production.
    """
    env = os.getenv("ENV", "development").lower()
    issues = []

    if not SECRET_KEY or SECRET_KEY in _INSECURE_DEFAULTS:
        issues.append(
            "JWT_SECRET_KEY is not set or uses an insecure default. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if not ADMIN_USERNAME:
        issues.append("ADMIN_USERNAME is not set.")
    if not ADMIN_PASSWORD_HASH:
        issues.append(
            "ADMIN_PASSWORD_HASH is not set. "
            "Generate one with: python -c \"import bcrypt; print(bcrypt.hashpw(b'PASSWORD', bcrypt.gensalt(12)).decode())\""
        )

    if issues:
        msg = "Auth configuration errors:\n" + "\n".join(f"  - {i}" for i in issues)
        if env == "production":
            raise RuntimeError(msg)
        else:
            logger.warning(msg + "\n  ⚠️  Admin panel will be non-functional until these are set.")

_validate_auth_config()

# ─────────────────────────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/admin/login")
router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_admin_user(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not SECRET_KEY or SECRET_KEY in _INSECURE_DEFAULTS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin auth not configured. Set JWT_SECRET_KEY in environment.",
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None or username != ADMIN_USERNAME:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username


@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Admin login endpoint. Credentials must be set via env vars."""
    if not ADMIN_USERNAME or not ADMIN_PASSWORD_HASH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin credentials not configured. Set ADMIN_USERNAME and ADMIN_PASSWORD_HASH.",
        )
    if form_data.username != ADMIN_USERNAME or not verify_password(form_data.password, ADMIN_PASSWORD_HASH):
        logger.warning(f"Failed admin login attempt for user: '{form_data.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": ADMIN_USERNAME},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    logger.info(f"Admin login successful for: {ADMIN_USERNAME}")
    return {"access_token": access_token, "token_type": "bearer"}
