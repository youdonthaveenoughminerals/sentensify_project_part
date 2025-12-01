import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient


MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")

SECRET_KEY = os.getenv("SECRET_KEY", "sentencify-dev-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_mongo_users_collection():
  client = MongoClient(MONGO_URI)
  db = client[MONGO_DB_NAME]
  return db["users"]


def hash_password(password: str) -> str:
  return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
  return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
  to_encode = data.copy()
  expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
  to_encode.update({"exp": expire})
  return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


class SignupRequest(BaseModel):
  email: EmailStr
  password: str


class LoginRequest(BaseModel):
  email: EmailStr
  password: str


class TokenResponse(BaseModel):
  access_token: str
  token_type: str = "bearer"
  user_id: str
  email: str


auth_router = APIRouter(tags=["auth"])


@auth_router.post("/signup")
def signup(req: SignupRequest) -> Dict[str, Any]:
  users = get_mongo_users_collection()

  existing = users.find_one({"email": req.email})
  if existing:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Email already registered",
    )

  user_doc: Dict[str, Any] = {
    "email": req.email,
    "password_hash": hash_password(req.password),
    "created_at": datetime.now(timezone.utc).isoformat(),
  }
  result = users.insert_one(user_doc)

  return {"id": str(result.inserted_id), "email": req.email}


@auth_router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest) -> TokenResponse:
  users = get_mongo_users_collection()
  user = users.find_one({"email": req.email})
  if not user:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials")

  password_hash = user.get("password_hash")
  if not password_hash or not verify_password(req.password, password_hash):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials")

  user_id = str(user.get("_id"))
  token_data = {
    "sub": req.email,
    "user_id": user_id,
  }
  access_token = create_access_token(token_data)
  return TokenResponse(
      access_token=access_token,
      user_id=user_id,
      email=req.email
  )

