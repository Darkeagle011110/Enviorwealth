import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorDatabase
from config.settings import settings
from models.mongodb import get_db
from models.schemas import ClientUserDoc

logger = logging.getLogger(__name__)

SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_expire_minutes * 24

client_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str
    full_name: str
    email: str

class UserSignup(BaseModel):
    full_name: str
    email: EmailStr
    password: str

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_client_user(token: str = Depends(client_oauth2_scheme), db: AsyncIOMotorDatabase = Depends(get_db)) -> ClientUserDoc:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user_dict = await db.client_users.find_one({"email": email})
    if user_dict is None:
        raise credentials_exception
    return ClientUserDoc(**user_dict)

@router.post("/signup", response_model=Token)
async def signup(user: UserSignup, db: AsyncIOMotorDatabase = Depends(get_db)):
    db_user = await db.client_users.find_one({"email": user.email})
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(user.password)
    new_user = ClientUserDoc(
        email=user.email,
        password_hash=hashed_password,
        full_name=user.full_name
    )
    await db.client_users.insert_one(new_user.model_dump())
    
    access_token = create_access_token(data={"sub": new_user.email})
    return {"access_token": access_token, "token_type": "bearer", "full_name": new_user.full_name, "email": new_user.email}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncIOMotorDatabase = Depends(get_db)):
    user_dict = await db.client_users.find_one({"email": form_data.username})
    if not user_dict or not verify_password(form_data.password, user_dict["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = ClientUserDoc(**user_dict)
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer", "full_name": user.full_name, "email": user.email}

@router.get("/me")
async def read_users_me(current_user: ClientUserDoc = Depends(get_current_client_user)):
    return {"id": current_user.id, "email": current_user.email, "full_name": current_user.full_name}
