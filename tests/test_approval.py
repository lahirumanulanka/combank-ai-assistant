import asyncio

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.core.rbac import Role
from app.graph.builder import build_graph
from app.graph.context import RuntimeContext
from app.tools.knowledge_search import make_knowledge_search
from app.tools.registry import AgentTool, ToolRegistry
from tests.fakes import FakeLLM, FakeSearcher
from tests.helpers import parse_sse

PURGE = [[{"name": "admin_purge_cache", "args": {"namespace": "payments"}}]]
DONE = "The payments cache was purged."


class CountingTool:
    def __init__(self):
        self.runs = 0

    async def run(self, args: dict, role: Role) -> dict:
        self.runs += 1
        return {"status": "done", **args}


def setup(role: Role):
    purge = CountingTool()
    searcher = FakeSearcher([0.9])
    registry = ToolRegistry([
        make_knowledge_search(searcher),
        AgentTool(name="admin_purge_cache", description="purge", parameters={"type": "object"}, run=purge.run),
    ])
    llm = FakeLLM(route="tool", answer=DONE, tool_script=PURGE)
    graph = build_graph(llm, searcher, checkpointer=InMemorySaver(), registry=registry)
    context = RuntimeContext(user_id=role.value, role=role, name="Test User")
    config = {"configurable": {"thread_id": f"{role.value}:t1"}}
    return graph, context, config, purge


def invoke(graph, graph_input, context, config) -> dict:
    return asyncio.run(graph.ainvoke(graph_input, config=config, context=context))


def ask_to_purge(graph, context, config) -> dict:
    return invoke(graph, {"messages": [HumanMessage("Purge the payments cache")]}, context, config)


def test_admin_action_pauses_before_running():
    graph, context, config, purge = setup(Role.ADMIN)

    result = ask_to_purge(graph, context, config)

    pause = result["__interrupt__"][0].value
    assert pause["actions"] == [{"tool": "admin_purge_cache", "args": {"namespace": "payments"}}]
    assert purge.runs == 0
    assert asyncio.run(graph.aget_state(config)).interrupts


def test_approved_action_runs_exactly_once():
    graph, context, config, purge = setup(Role.ADMIN)
    ask_to_purge(graph, context, config)

    result = invoke(graph, Command(resume={"approved": True}), context, config)

    assert purge.runs == 1
    assert result["tool_results"] == [{"tool": "admin_purge_cache", "args": {"namespace": "payments"},
                                       "status": "ok"}]
    assert result["messages"][-1].content == DONE


def test_rejected_action_never_runs():
    graph, context, config, purge = setup(Role.ADMIN)
    ask_to_purge(graph, context, config)

    result = invoke(graph, Command(resume={"approved": False}), context, config)

    assert purge.runs == 0
    assert result["tool_results"][0]["status"] == "rejected"


def test_non_admin_is_denied_without_asking_for_approval():
    graph, context, config, purge = setup(Role.ANALYST)

    result = ask_to_purge(graph, context, config)

    assert "__interrupt__" not in result
    assert result["tool_results"][0]["status"] == "denied"
    assert purge.runs == 0


@pytest.fixture
def admin_client(client):
    graph, _, _, purge = setup(Role.ADMIN)
    client.app.state.graph = graph
    client.purge = purge
    token = client.post("/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_api_streams_the_pause_and_resumes_after_approval(admin_client):
    first = parse_sse(admin_client.post("/chat/stream", json={"message": "Purge payments cache",
                                                               "thread_id": "t1"}).text)
    names = [name for name, _ in first]
    assert "interrupt" in names
    done = first[-1][1]
    assert (done["answer"], done["awaiting_approval"]) == ("", True)
    assert len(done["run_id"]) == 36

    second = parse_sse(admin_client.post("/chat/resume", json={"thread_id": "t1", "approved": True}).text)

    assert admin_client.purge.runs == 1
    assert second[-1][1]["answer"] == DONE


def test_api_blocks_new_messages_while_an_action_is_waiting(admin_client):
    admin_client.post("/chat/stream", json={"message": "Purge payments cache", "thread_id": "t1"})

    response = admin_client.post("/chat/stream", json={"message": "hello", "thread_id": "t1"})

    assert response.status_code == 409
    assert response.json()["error"] == "approval_conflict"


def test_api_resume_without_a_pending_action_is_rejected(admin_client):
    response = admin_client.post("/chat/resume", json={"thread_id": "nothing-here", "approved": True})

    assert response.status_code == 409
