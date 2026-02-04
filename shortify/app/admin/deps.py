from typing import Annotated

from fastapi import Depends, Request
from jose import JWTError, jwt
from pydantic import ValidationError

from shortify.app.core import security
from shortify.app.core.config import settings
from shortify.app.models import User
from shortify.app.schemas.token import AuthTokenPayload


class AdminAuthError(Exception):
    pass


async def get_current_admin_user(request: Request) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise AdminAuthError

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[security.ALGORITHM],
        )
        token_data = AuthTokenPayload(**payload)
    except (JWTError, ValidationError):
        raise AdminAuthError from None

    user = await User.get(token_data.sub)
    if not user:
        raise AdminAuthError

    if not user.is_active or not user.is_superuser:
        raise AdminAuthError

    return user


CurrentAdminUser = Annotated[User, Depends(get_current_admin_user)]
