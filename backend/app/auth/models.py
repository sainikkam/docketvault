from typing import Literal, Optional
from uuid import UUID

from sqlmodel import Field, SQLModel

from app.base_model import BaseID


class User(BaseID, table=True):
    __tablename__ = "users"
    email: str = Field(unique=True, index=True, max_length=255)
    password_hash: str = Field(max_length=255)
    role: str = Field(max_length=50)
    display_name: str = Field(max_length=255)
    # MFA columns present for future use — not implemented in MVP
    mfa_secret: Optional[str] = Field(default=None, max_length=255)
    mfa_enabled: bool = Field(default=False)
    # Auto-verified in MVP (set True on registration)
    email_verified: bool = Field(default=True)


class RegisterRequest(SQLModel):
    email: str
    password: str
    role: Literal["primary_client", "contributor_client", "attorney", "paralegal"]
    display_name: str


class LoginRequest(SQLModel):
    email: str
    password: str


class TokenResponse(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(SQLModel):
    id: UUID
    email: str
    role: str
    display_name: str
    email_verified: bool


class UserUpdateRequest(SQLModel):
    display_name: Optional[str] = None
