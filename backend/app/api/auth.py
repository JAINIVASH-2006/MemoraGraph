"""
MemoraGraph API – Authentication Endpoints

POST /api/auth/register  – Create new user account
POST /api/auth/login     – Authenticate and receive JWT token
GET  /api/auth/me        – Get current user profile
"""

import logging
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_session
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut, ChangePasswordRequest
from app.security.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Register a new user. Returns a JWT token immediately."""
    # Check if email already exists
    result = await session.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Validate role
    try:
        role = UserRole(body.role.upper() if body.role else "EMPLOYEE")
    except ValueError:
        role = UserRole.EMPLOYEE

    # Create user
    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    logger.info("New user registered: %s (role=%s)", user.email, user.role)

    token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role.value},
        expires_delta=timedelta(minutes=settings.jwt_expiration_minutes),
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Authenticate with email/password. Returns a JWT token."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    logger.info("User logged in: %s", user.email)

    token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role.value},
        expires_delta=timedelta(minutes=settings.jwt_expiration_minutes),
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Return the currently authenticated user's profile."""
    return UserOut.model_validate(current_user)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Change the current user's password."""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    # Re-fetch for update
    result = await session.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    user.hashed_password = hash_password(body.new_password)
    logger.info("Password changed for user: %s", user.email)


from pydantic import BaseModel
from typing import Optional

class FirebaseSyncRequest(BaseModel):
    id_token: str
    name: Optional[str] = None
    role: Optional[str] = "EMPLOYEE"


@router.post("/firebase-sync", response_model=TokenResponse)
async def sync_firebase_user(
    body: FirebaseSyncRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Sync a user authenticated via Firebase and return a local access token."""
    from app.security.auth import decode_token
    payload = decode_token(body.id_token)
    email = payload.get("email")
    user_id = payload.get("sub") or payload.get("user_id")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firebase token does not contain a valid email address.",
        )

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        try:
            role = UserRole(body.role.upper() if body.role else "EMPLOYEE")
        except ValueError:
            role = UserRole.EMPLOYEE

        user_name = body.name or payload.get("name") or email.split("@")[0].capitalize()
        user = User(
            id=user_id or str(uuid.uuid4()),
            email=email,
            hashed_password=hash_password(str(uuid.uuid4())),
            name=user_name,
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        logger.info("Created new user from Firebase: %s", user.email)

    token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role.value},
        expires_delta=timedelta(minutes=settings.jwt_expiration_minutes),
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_minutes * 60,
        user=UserOut.model_validate(user),
    )
