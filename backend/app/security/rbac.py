"""
MemoraGraph – Role-Based Access Control
"""

from fastapi import Depends, HTTPException, status
from typing import Callable

from app.models.user import User, UserRole
from app.security.auth import get_current_user


def require_roles(*roles: UserRole) -> Callable:
    """
    FastAPI dependency factory.
    Usage: Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
    """
    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user
    return check_role


# Convenience shortcuts
require_admin = require_roles(UserRole.ADMIN)
require_manager_or_admin = require_roles(UserRole.ADMIN, UserRole.MANAGER)
require_any_role = require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.EMPLOYEE)
