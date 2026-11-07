import math
from typing import Annotated

import structlog
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import RateLimited, Unauthorized
from app.core.logging import get_logger
from app.core.ratelimit import get_rate_limiter
from app.core.security import InvalidTokenError, decode_access_token
from app.core.users import User, get_user

log = get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise Unauthorized("Missing bearer token")

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise Unauthorized("Invalid or expired token") from None

    user = get_user(payload["sub"])
    if user is None:
        raise Unauthorized("User no longer exists")

    structlog.contextvars.bind_contextvars(user=user.username, role=user.role.value)
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def rate_limited_user(user: CurrentUser) -> User:
    result = get_rate_limiter().check(user.username, user.role)
    if result.allowed:
        return user

    retry_after = math.ceil(result.retry_after_s)
    log.warning("rate_limited", retry_after=retry_after)
    raise RateLimited(retry_after)


RateLimitedUser = Annotated[User, Depends(rate_limited_user)]
