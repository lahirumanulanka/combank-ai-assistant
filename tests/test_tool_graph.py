import asyncio

from langchain_core.messages import HumanMessage

from app.core.rbac import Role
from app.graph.builder import build_graph
from app.graph.context import RuntimeContext
from app.tools.knowledge_search import make_knowledge_search
from app.tools.registry import AgentTool, ToolRegistry
from mcp_server import directory
from tests.fakes import FakeLLM, FakeSearcher

ANSWER = "Kasun Jayasinghe is on call (service catalog). Certificate steps: [POL-SEC-001#4]."
PLAIN_ANSWER = "Kasun Jayasinghe is on call (service catalog)."


def mcp_tool(name: str, function) -> AgentTool:
    async def run(args: dict, role: Role):
        return function(**args)

    return AgentTool(name=name, description=name, parameters={"type": "object"}, run=run, source="mcp")


def registry(searcher, mcp_available: bool = True) -> ToolRegistry:
    tools = [make_knowledge_search(searcher)]
    if mcp_available:
        tools += [mcp_tool("get_service", directory.get_service),
                  mcp_tool("lookup_employee", directory.lookup_employee)]
    return ToolRegistry(tools, mcp_available=mcp_available)


SCRIPT = [[{"name": "get_service", "args": {"name": "payment-gateway"}},
           {"name": "knowledge_search", "args": {"query": "payment gateway runbook"}}]]


def run(role: Role, script=SCRIPT, mcp_available: bool = True, answer: str = ANSWER) -> tuple[dict, FakeLLM]:
    searcher = FakeSearcher([0.9])
    llm = FakeLLM(route="tool", answer=answer, tool_script=script)
    graph = build_graph(llm, searcher, registry=registry(searcher, mcp_available))
    context = RuntimeContext(user_id=role.value, role=role, name="Test User")
    result = asyncio.run(graph.ainvoke({"messages": [HumanMessage("Who is on call for payment-gateway?")]},
                                       context=context))
    return result, llm


def test_analyst_calls_two_tools_in_one_round_then_answers():
    result, llm = run(Role.ANALYST)

    assert llm.bound_tools[0] == ["knowledge_search", "get_service", "lookup_employee"]
    assert [(r["tool"], r["status"]) for r in result["tool_results"]] == [("get_service", "ok"),
                                                                         ("knowledge_search", "ok")]
    assert result["validation"]["ok"]
    assert result["messages"][-1].content == ANSWER


def test_tool_results_go_back_to_the_agent_as_tool_messages():
    result, _ = run(Role.ANALYST)

    tool_message = next(m for m in result["tool_messages"] if m.type == "tool" and m.name == "get_service")
    assert "Kasun Jayasinghe" in tool_message.content


def test_viewer_is_only_given_knowledge_search():
    _, llm = run(Role.VIEWER, script=[])

    assert llm.bound_tools[0] == ["knowledge_search"]


def test_viewer_cannot_run_a_tool_even_if_the_model_calls_it():
    result, _ = run(Role.VIEWER)

    statuses = {r["tool"]: r["status"] for r in result["tool_results"]}
    assert statuses == {"get_service": "denied", "knowledge_search": "ok"}


def test_mcp_down_is_told_to_the_agent_and_tools_are_missing():
    result, llm = run(Role.ANALYST, script=[], mcp_available=False, answer=PLAIN_ANSWER)

    assert llm.bound_tools[0] == ["knowledge_search"]
    assert "unavailable right now" in llm.system_prompts[-1]
    assert result["validation"]["ok"]


def test_tool_loop_stops_after_three_rounds():
    endless = [[{"name": "get_service", "args": {"name": "payment-gateway"}}]] * 10

    result, llm = run(Role.ANALYST, script=endless, answer=PLAIN_ANSWER)

    assert len(llm.bound_tools) == 3
    assert result["messages"][-1].content == PLAIN_ANSWER


def test_tool_answer_cannot_cite_a_document_it_never_searched():
    result, _ = run(Role.ANALYST, script=[[{"name": "get_service", "args": {"name": "payment-gateway"}}]])

    assert result["validation"]["unknown"] == ["POL-SEC-001#4"]
    assert "could not produce an answer with verified sources" in result["messages"][-1].content
