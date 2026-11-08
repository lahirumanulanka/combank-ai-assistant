from datetime import UTC, datetime
from typing import get_args

from pydantic import BaseModel, ConfigDict, Field

from app.core.logging import get_logger
from app.core.rbac import Role
from app.knowledge.documents import Department
from app.tools.registry import AgentTool

log = get_logger(__name__)


class NamespaceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: Department = Field(description=f"One of: {', '.join(get_args(Department))}")


def _mock_action(action: str, description: str) -> AgentTool:
    async def run(args: dict, role: Role) -> dict:
        parsed = NamespaceArgs.model_validate(args)
        log.warning("admin_action_executed", action=action, namespace=parsed.namespace, role=role.value)
        return {"status": "done", "action": action, "namespace": parsed.namespace,
                "at": datetime.now(UTC).isoformat(timespec="seconds"), "note": "mock action for the demo"}

    return AgentTool(name=action, description=description, parameters=NamespaceArgs.model_json_schema(), run=run)


def make_admin_tools() -> list[AgentTool]:
    return [
        _mock_action("admin_purge_cache", "Admin only. Purge the retrieval cache for one namespace. Needs human approval."),
        _mock_action("admin_reindex_namespace", "Admin only. Re-index all documents in one namespace. Needs human approval."),
    ]
