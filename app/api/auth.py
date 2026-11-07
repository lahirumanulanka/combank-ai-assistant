from fastapi import APIRouter

from app.api.deps import RateLimitedUser
from app.api.schemas import LoginRequest, MeResponse, TokenResponse
from app.core.errors import Unauthorized
from app.core.logging import get_logger
from app.core.rbac import allowed_access_levels
from app.core.security import create_access_token
from app.core.users import authenticate

log = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    user = authenticate(body.username, body.password)
    if user is None:
        log.warning("login_failed", username=body.username)
        raise Unauthorized("Wrong username or password")

    log.info("login_succeeded", user=user.username, role=user.role.value)
    token = create_access_token(user.username, user.role)
    return TokenResponse(access_token=token, role=user.role, name=user.name)


@router.get("/me", response_model=MeResponse)
async def me(user: RateLimitedUser) -> MeResponse:
    return MeResponse(
        username=user.username,
        name=user.name,
        role=user.role,
        access_levels=allowed_access_levels(user.role),
    )
