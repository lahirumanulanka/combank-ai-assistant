import math
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.ratelimit import get_rate_limiter
from app.core.security import InvalidTokenError, decode_access_token
from app.core.users import User, get_user

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise _unauthorized("Missing bearer token")

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise _unauthorized("Invalid or expired token") from None

    user = get_user(payload["sub"])
    if user is None:
        raise _unauthorized("User no longer exists")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def rate_limited_user(user: CurrentUser) -> User:
    result = get_rate_limiter().check(user.username, user.role)
    if result.allowed:
        return user

    retry_after = math.ceil(result.retry_after_s)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "rate_limited",
            "message": f"Too many requests. Please wait {retry_after} seconds.",
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


RateLimitedUser = Annotated[User, Depends(rate_limited_user)]
