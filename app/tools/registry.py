import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from langsmith import traceable
from pydantic import ValidationError

from app.core.logging import get_logger
from app.core.rbac import Role, can_use_tool, lowest_role_for
from app.core.tracing import without_self

log = get_logger(__name__)

MAX_TOOL_OUTPUT_CHARS = 6000

Status = Literal["ok", "denied", "invalid", "timeout", "error", "unknown", "rejected"]


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    parameters: dict
    run: Callable[[dict, Role], Awaitable[Any]]
    source: str = "local"

    def spec(self) -> dict:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


@dataclass(frozen=True)
class ToolOutcome:
    status: Status
    content: str
    data: Any = None


class ToolRegistry:
    def __init__(self, tools: list[AgentTool], timeout_s: float = 10, mcp_available: bool = False,
                 chaos_delay_s: float = 0):
        self._tools = {tool.name: tool for tool in tools}
        self.timeout_s = timeout_s
        self.mcp_available = mcp_available
        self.chaos_delay_s = chaos_delay_s

    def tools_for(self, role: Role) -> list[AgentTool]:
        return [tool for name, tool in self._tools.items() if can_use_tool(role, name)]

    def locked_for(self, role: Role) -> list[str]:
        return [f"{name} (needs {lowest_role_for(name).value})" for name in self._tools if not can_use_tool(role, name)]

    @traceable(run_type="tool", name="tool_execute", process_inputs=without_self)
    async def execute(self, name: str, args: dict, role: Role) -> ToolOutcome:
        tool = self._tools.get(name)
        if tool is None:
            return ToolOutcome("unknown", f"Tool '{name}' does not exist or is unavailable right now.")
        if not can_use_tool(role, name):
            log.warning("tool_denied", tool=name, role=role.value)
            return ToolOutcome("denied", f"Tool '{name}' is not permitted for the {role.value} role.")

        try:
            data = await asyncio.wait_for(self._run(tool, args, role), timeout=self.timeout_s)
        except ValidationError as exc:
            return ToolOutcome("invalid", f"Invalid arguments for '{name}': {exc.errors(include_url=False)}")
        except TimeoutError:
            log.warning("tool_timeout", tool=name)
            return ToolOutcome("timeout", f"Tool '{name}' timed out after {self.timeout_s:.0f}s.")
        except Exception as exc:  # noqa: BLE001 - a broken tool must not crash the conversation
            log.warning("tool_failed", tool=name, error=type(exc).__name__)
            return ToolOutcome("error", f"Tool '{name}' failed ({type(exc).__name__}). Continue without it.")

        content = data if isinstance(data, str) else json.dumps(data, default=str)
        log.info("tool_ok", tool=name)
        return ToolOutcome("ok", content[:MAX_TOOL_OUTPUT_CHARS], data)

    async def _run(self, tool: AgentTool, args: dict, role: Role):
        if self.chaos_delay_s:
            await asyncio.sleep(self.chaos_delay_s)
        return await tool.run(args, role)
