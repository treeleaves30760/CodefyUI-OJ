from app.core.security import fastapi_users
from app.schemas.user import UserRead, UserUpdate

router = fastapi_users.get_users_router(UserRead, UserUpdate)
