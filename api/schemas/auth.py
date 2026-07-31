"""Pydantic schemas for Auth endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class SendVerificationCodeRequest(BaseModel):
    email: str
    password: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


class AccountDeletePasswordRequest(BaseModel):
    password: str


class AccountDeleteVerifyRequest(BaseModel):
    code: str


class UserOAuthProvidersResponse(BaseModel):
    has_oauth: bool
    providers: list[str]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
