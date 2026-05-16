from fastapi import Depends, HTTPException, status

from app.core.security import current_active_user
from app.models.user import User, UserRole


def role_required(*roles: UserRole):
    async def check(user: User = Depends(current_active_user)) -> User:
        if user.is_superuser or user.role in roles:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires role: {', '.join(r.value for r in roles)}",
        )

    return check


require_teacher = role_required(UserRole.teacher, UserRole.admin)
require_admin = role_required(UserRole.admin)
