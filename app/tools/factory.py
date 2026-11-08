from app.core.config import Settings
from app.services.mcp_client import load_mcp_tools
from app.tools.knowledge_search import make_knowledge_search
from app.tools.registry import ToolRegistry


async def build_tool_registry(settings: Settings, searcher) -> ToolRegistry:
    mcp_tools = await load_mcp_tools(settings.mcp_url, settings.mcp_timeout_s)
    return ToolRegistry(
        [make_knowledge_search(searcher), *mcp_tools],
        timeout_s=settings.tool_timeout_s,
        mcp_available=bool(mcp_tools),
    )
