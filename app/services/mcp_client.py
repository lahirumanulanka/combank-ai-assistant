import asyncio

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.core.logging import get_logger
from app.core.rbac import Role
from app.tools.registry import AgentTool

log = get_logger(__name__)


def _parameters(tool: BaseTool) -> dict:
    schema = tool.args_schema
    return schema if isinstance(schema, dict) else schema.model_json_schema()


def _to_agent_tool(tool: BaseTool) -> AgentTool:
    async def run(args: dict, role: Role):
        return await tool.ainvoke(args)

    return AgentTool(name=tool.name, description=tool.description, parameters=_parameters(tool), run=run, source="mcp")


async def load_mcp_tools(url: str, timeout_s: float) -> list[AgentTool]:
    client = MultiServerMCPClient({"enterprise": {"url": url, "transport": "streamable_http"}})
    try:
        tools = await asyncio.wait_for(client.get_tools(), timeout=timeout_s)
    except Exception as exc:  # noqa: BLE001 - MCP being down must not stop the assistant
        log.warning("mcp_unavailable", url=url, error=type(exc).__name__)
        return []

    log.info("mcp_tools_loaded", tools=[tool.name for tool in tools])
    return [_to_agent_tool(tool) for tool in tools]
