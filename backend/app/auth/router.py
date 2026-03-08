from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    User,
    UserResponse,
    UserUpdateRequest,
)
from app.auth.service import get_current_user, login, refresh_access_token, register
from app.database import get_db

router = APIRouter()


@router.post("/auth/register", response_model=TokenResponse)
async def register_endpoint(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await register(req, db)


@router.post("/auth/login", response_model=TokenResponse)
async def login_endpoint(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login(req, db)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_endpoint(
    refresh_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    return await refresh_access_token(refresh_token, db)


@router.get("/users/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/users/me", response_model=UserResponse)
async def update_me(
    update: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if update.display_name is not None:
        current_user.display_name = update.display_name
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user
