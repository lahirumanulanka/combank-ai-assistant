from fastapi import APIRouter, Request

from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])

CHAOS_FLAGS = ["chaos_llm_fail", "chaos_pinecone_fail", "chaos_mcp_down", "chaos_tool_slow_ms", "chaos_fake_citation"]


@router.get("")
async def health(request: Request) -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "assistant": "ready" if request.app.state.graph is not None else "not configured",
        "models": {"strong": settings.llm_strong, "cheap": settings.llm_cheap, "fallback": settings.llm_fallback or None},
        "chaos": [flag for flag in CHAOS_FLAGS if getattr(settings, flag)],
    }
