from typing import Optional
from datetime import datetime
import uuid
from sqlmodel import SQLModel, Field
from pydantic import BaseModel

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_admin: bool = Field(default=False)
    is_verified: bool = Field(default=False)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    is_admin: bool = False
    is_verified: bool = False

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
