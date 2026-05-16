from fastapi_users import schemas

from app.models.user import UserRole


class UserRead(schemas.BaseUser[int]):
    display_name: str = ""
    role: UserRole = UserRole.student


class UserCreate(schemas.BaseUserCreate):
    display_name: str = ""


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None
