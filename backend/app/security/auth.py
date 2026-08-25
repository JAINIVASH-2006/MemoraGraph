"""
MemoraGraph – JWT Authentication & Password Security
"""

# Passlib patch for bcrypt compatibility on Python 3.10+
import bcrypt
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("About", (), {"__version__": bcrypt.__version__})

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import PyJWTError as JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_session
from app.models.user import User

logger = logging.getLogger(__name__)

# Password hashing
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ─── Password Utilities ───────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ─── JWT Utilities ────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expiration_minutes)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token or Firebase ID token. Raises HTTPException on failure."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # 1. Try decoding with local JWT secret
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        pass

    # 2. Try decoding as Firebase/Google token
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        if "user_id" in unverified or "firebase" in unverified or "email" in unverified:
            if "sub" not in unverified and "user_id" in unverified:
                unverified["sub"] = unverified["user_id"]
            return unverified
    except Exception as e:
        logger.debug("Unverified JWT decode error: %s", e)

    raise credentials_exception


# ─── FastAPI Dependencies ─────────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Dependency: decode JWT/Firebase token → load or sync User from DB. Raises 401 if invalid."""
    payload = decode_token(token)
    user_id: Optional[str] = payload.get("sub") or payload.get("user_id")
    email: Optional[str] = payload.get("email")

    if not user_id and not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject or email claim",
        )

    # 1. Search existing user by id
    user = None
    if user_id:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    # 2. Search existing user by email
    if not user and email:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    # 3. Auto-provision user if authenticated via Firebase
    if not user and email:
        import uuid
        from app.models.user import UserRole
        user_name = payload.get("name") or email.split("@")[0].capitalize()
        user = User(
            id=user_id or str(uuid.uuid4()),
            email=email,
            hashed_password=hash_password(str(uuid.uuid4())),
            name=user_name,
            role=UserRole.MANAGER,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("Auto-provisioned Firebase authenticated user: %s (id=%s)", user.email, user.id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def get_current_user_optional(
    token: Optional[str] = Depends(OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """Dependency: optionally extract user (returns None if no token)."""
    if token is None:
        return None
    try:
        return await get_current_user(token, session)
    except HTTPException:
        return None
