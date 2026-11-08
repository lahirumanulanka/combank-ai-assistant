from app.core.config import Settings
from app.knowledge.catalog import Library
from app.services.mcp_client import load_mcp_tools
from app.tools.admin_tools import make_admin_tools
from app.tools.knowledge_search import make_knowledge_search
from app.tools.python_analysis import make_python_analysis
from app.tools.registry import ToolRegistry


async def build_tool_registry(settings: Settings, searcher, library: Library) -> ToolRegistry:
    mcp_tools = [] if settings.chaos_mcp_down else await load_mcp_tools(settings.mcp_url, settings.mcp_timeout_s)
    return ToolRegistry(
        [make_knowledge_search(searcher), make_python_analysis(library), *mcp_tools, *make_admin_tools()],
        timeout_s=settings.tool_timeout_s,
        mcp_available=bool(mcp_tools),
        chaos_delay_s=settings.chaos_tool_slow_ms / 1000,
    )
