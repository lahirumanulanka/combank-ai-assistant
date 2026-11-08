import asyncio

import pytest

from app.core.rbac import Role
from app.guards.citations import check_citations
from app.tools.knowledge_search import make_knowledge_search
from app.tools.registry import AgentTool, ToolRegistry
from mcp_server import directory
from tests.fakes import FakeSearcher


def tool(name: str, result=None, delay: float = 0, error: Exception | None = None) -> AgentTool:
    async def run(args: dict, role: Role):
        await asyncio.sleep(delay)
        if error:
            raise error
        return result if result is not None else {"tool": name, "args": args}

    return AgentTool(name=name, description=name, parameters={"type": "object", "properties": {}}, run=run)


REGISTRY = ToolRegistry([tool("knowledge_search"), tool("get_service"), tool("lookup_employee")], timeout_s=0.2)


def execute(name: str, role: Role, registry: ToolRegistry = REGISTRY, args: dict | None = None):
    return asyncio.run(registry.execute(name, args or {}, role))


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.VIEWER, ["knowledge_search"]),
        (Role.ANALYST, ["knowledge_search", "get_service", "lookup_employee"]),
        (Role.ADMIN, ["knowledge_search", "get_service", "lookup_employee"]),
    ],
)
def test_each_role_only_sees_its_tools(role, expected):
    assert [t.name for t in REGISTRY.tools_for(role)] == expected


def test_executor_checks_the_role_again_even_if_the_ai_asks():
    outcome = execute("get_service", Role.VIEWER)

    assert outcome.status == "denied"
    assert "not permitted for the viewer role" in outcome.content


def test_allowed_tool_returns_json_content():
    outcome = execute("get_service", Role.ANALYST, args={"name": "payment-gateway"})

    assert outcome.status == "ok"
    assert '"payment-gateway"' in outcome.content


def test_slow_tool_times_out():
    registry = ToolRegistry([tool("get_service", delay=1)], timeout_s=0.05)

    assert execute("get_service", Role.ANALYST, registry).status == "timeout"


def test_broken_tool_becomes_an_error_message_not_a_crash():
    registry = ToolRegistry([tool("get_service", error=ConnectionError("mcp down"))])

    outcome = execute("get_service", Role.ANALYST, registry)

    assert outcome.status == "error"
    assert "mcp down" not in outcome.content


def test_unknown_tool_is_reported():
    assert execute("admin_purge_cache", Role.ADMIN).status == "unknown"


def test_knowledge_search_rejects_extra_arguments():
    registry = ToolRegistry([make_knowledge_search(FakeSearcher([0.9]))])

    outcome = execute("knowledge_search", Role.VIEWER, registry, args={"query": "pw", "access_level": "restricted"})

    assert outcome.status == "invalid"


def test_knowledge_search_returns_citable_passages_above_min_score():
    registry = ToolRegistry([make_knowledge_search(FakeSearcher([0.9, 0.1]))])

    outcome = execute("knowledge_search", Role.VIEWER, registry, args={"query": "password"})

    assert [p["chunk_id"] for p in outcome.data] == ["POL-SEC-001#4"]


def test_directory_finds_who_is_on_call():
    names = [e["name"] for e in directory.lookup_employee(on_call_for="payment-gateway")]

    assert names == ["Kasun Jayasinghe"]


def test_service_catalog_includes_on_call_engineer():
    service = directory.get_service("payment-gateway")

    assert service["owner_team"] == "payments-platform"
    assert service["on_call"][0]["name"] == "Kasun Jayasinghe"


def test_unknown_service_lists_the_known_ones():
    assert "payment-gateway" in directory.get_service("nope")["known_services"]


def test_incident_records_match_the_incident_documents():
    records = directory.list_incident_records(service="payment-gateway", severity="SEV1")

    assert [r["id"] for r in records["records"]] == ["INC-2025-12-24", "INC-2026-07-21"]


def test_tool_answers_may_skip_citations_but_not_invent_them():
    assert check_citations("Kasun is on call (service catalog).", [], require=False).ok
    assert not check_citations("See [INC-1999-01-01#9].", [], require=False).ok


def test_viewer_is_told_which_tools_are_locked():
    assert REGISTRY.locked_for(Role.VIEWER) == ["get_service (needs analyst)", "lookup_employee (needs analyst)"]
    assert REGISTRY.locked_for(Role.ANALYST) == []
