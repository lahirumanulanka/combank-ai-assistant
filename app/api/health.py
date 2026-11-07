from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name}
