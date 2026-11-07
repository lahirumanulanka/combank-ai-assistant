from fastapi import APIRouter, HTTPException, status

from app.api.deps import RateLimitedUser
from app.api.schemas import LoginRequest, MeResponse, TokenResponse
from app.core.rbac import allowed_access_levels
from app.core.security import create_access_token
from app.core.users import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    user = authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong username or password")

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
