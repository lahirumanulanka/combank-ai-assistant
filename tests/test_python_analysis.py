import asyncio

import pytest
from langchain_core.messages import HumanMessage

from app.core.rbac import Role
from app.graph.builder import build_graph
from app.graph.context import RuntimeContext
from app.knowledge.catalog import Library
from app.tools.python_analysis import make_python_analysis
from app.tools.registry import ToolRegistry
from scripts.generate_incidents import main as generate_incidents
from tests.fakes import FakeLLM, FakeSearcher


@pytest.fixture(scope="module")
def library(tmp_path_factory) -> Library:
    folder = tmp_path_factory.mktemp("data")
    generate_incidents(folder)
    return Library.from_folder(folder / "docs")


def run(library: Library, args: dict, role: Role = Role.ANALYST):
    registry = ToolRegistry([make_python_analysis(library)])
    return asyncio.run(registry.execute("python_analysis", args, role))


def test_counts_payment_incidents_by_severity_in_the_last_year(library):
    outcome = run(library, {"operation": "count_by", "field": "severity", "tag": "payments", "since": "2025-11-07"})

    assert outcome.status == "ok"
    assert outcome.data["rows_used"] == 12
    assert outcome.data["result"] == [{"severity": "SEV2", "count": 6}, {"severity": "SEV3", "count": 4},
                                      {"severity": "SEV1", "count": 2}]


def test_timeline_is_sorted_by_month(library):
    outcome = run(library, {"operation": "timeline", "tag": "payments", "since": "2026-06-01"})

    assert [row["month"] for row in outcome.data["result"]] == ["2026-06", "2026-07", "2026-08", "2026-09"]


def test_list_filters_by_service_and_severity(library):
    outcome = run(library, {"operation": "list", "service": "payment-gateway", "severity": "SEV1"})

    assert outcome.data["source_documents"] == ["INC-2025-12-24", "INC-2026-07-21"]


def test_confidential_incident_is_counted_for_analyst_only(library):
    analyst = run(library, {"operation": "count_by", "field": "service"})
    admin = run(library, {"operation": "count_by", "field": "service"}, role=Role.ADMIN)

    assert "INC-2026-02-27" in analyst.data["source_documents"]
    assert analyst.data["rows_used"] == admin.data["rows_used"] == 16


def test_viewer_cannot_use_the_tool(library):
    assert run(library, {"operation": "timeline"}, role=Role.VIEWER).status == "denied"


@pytest.mark.parametrize(
    "args",
    [
        {"operation": "exec", "field": "service"},
        {"operation": "count_by", "field": "password"},
        {"operation": "list", "code": "import os"},
        {"operation": "list", "since": "last year"},
    ],
)
def test_only_known_operations_and_fields_are_accepted(library, args):
    assert run(library, args).status == "invalid"


def test_tool_agent_can_call_python_analysis(library):
    script = [[{"name": "python_analysis",
                "args": {"operation": "count_by", "field": "severity", "tag": "payments", "since": "2025-11-07"}}]]
    llm = FakeLLM(route="tool", answer="SEV2: 6, SEV3: 4, SEV1: 2 (python_analysis).", tool_script=script)
    graph = build_graph(llm, FakeSearcher([0.9]), library=library)
    context = RuntimeContext(user_id="analyst", role=Role.ANALYST, name="Test User")

    result = asyncio.run(graph.ainvoke({"messages": [HumanMessage("Incidents per severity?")]}, context=context))

    assert "python_analysis" in llm.bound_tools[0]
    assert result["tool_results"] == [{"tool": "python_analysis", "args": script[0][0]["args"], "status": "ok"}]
    assert result["validation"]["ok"]


def test_no_match_returns_a_hint_with_valid_values(library):
    outcome = run(library, {"operation": "timeline", "service": "payment"})

    assert outcome.data["rows_used"] == 0
    assert "payment-gateway" in outcome.data["services"]
    assert "payments" in outcome.data["tags"]
