import asyncio
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.core.errors import LLMUnavailable
from app.core.rbac import Role
from app.graph import prompts
from app.graph.builder import build_graph
from app.graph.context import RuntimeContext
from app.knowledge.catalog import Library
from app.services.llm import BrokenModel, FallbackModel
from app.services.local_search import LocalSearch
from app.services.resilience import CircuitBreaker
from app.services.resilient_search import ResilientSearch
from app.tools.registry import AgentTool, ToolRegistry
from tests.fakes import GOOD_ANSWER, FakeLLM, FakeSearcher


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(scope="module")
def local_search() -> LocalSearch:
    return LocalSearch.from_library(Library.from_folder(Path("data/docs")))


class DeadPinecone:
    def __init__(self):
        self.calls = 0

    async def search(self, query, role, **filters):
        self.calls += 1
        raise ConnectionError("pinecone down")


def test_breaker_opens_after_repeated_failures_and_closes_after_cooldown():
    clock = FakeClock()
    breaker = CircuitBreaker(failures_to_open=3, cooldown_s=30, clock=clock)

    for _ in range(3):
        breaker.record_failure()
    assert breaker.is_open()

    clock.now += 31
    assert not breaker.is_open()

    breaker.record_success()
    assert not breaker.is_open()


def test_local_search_finds_the_password_policy(local_search):
    results = local_search.search("password rotation 90 days", Role.VIEWER)

    assert results[0].doc_id == "POL-SEC-001"
    assert results[0].source == "local_bm25"


def test_local_search_still_applies_the_role_filter(local_search):
    viewer = {r.doc_id for r in local_search.search("salary bands engineering", Role.VIEWER)}
    admin = {r.doc_id for r in local_search.search("salary bands engineering", Role.ADMIN)}

    assert "HR-COMP-001" not in viewer
    assert "HR-COMP-001" in admin


def test_dead_pinecone_falls_back_to_local_search_and_then_stops_calling_it(local_search):
    pinecone = DeadPinecone()
    search = ResilientSearch(pinecone, local_search, CircuitBreaker(failures_to_open=2), timeout_s=1)

    for _ in range(4):
        results = asyncio.run(search.search("password rotation", Role.VIEWER))
        assert results[0].source == "local_bm25"

    assert pinecone.calls == 2


def test_chaos_switch_skips_pinecone(local_search):
    pinecone = FakeSearcher([0.9])
    search = ResilientSearch(pinecone, local_search, CircuitBreaker(), timeout_s=1, chaos=True)

    results = asyncio.run(search.search("password rotation", Role.VIEWER))

    assert pinecone.calls == []
    assert results[0].source == "local_bm25"


def test_degraded_search_is_flagged_and_told_to_the_model(local_search):
    llm = FakeLLM(answer="Passwords rotate every 90 days [POL-SEC-001#4].")
    searcher = ResilientSearch(DeadPinecone(), local_search, CircuitBreaker(), timeout_s=1)
    graph = build_graph(llm, searcher)
    context = RuntimeContext(user_id="viewer", role=Role.VIEWER, name="Test User")

    result = asyncio.run(graph.ainvoke({"messages": [HumanMessage("password policy?")]}, context=context))

    assert result["degraded"]
    assert "backup mode" in llm.system_prompts[-1]


class WorkingModel:
    def __init__(self, answer: str):
        self.answer = answer

    async def ainvoke(self, messages, **kwargs):
        return AIMessage(self.answer)

    def with_structured_output(self, schema):
        return self

    def bind_tools(self, tools):
        return self


def test_backup_model_answers_when_the_main_one_fails():
    model = FallbackModel(BrokenModel(), WorkingModel("from backup"), "openai:backup")

    assert asyncio.run(model.ainvoke([("user", "hi")])).content == "from backup"
    assert asyncio.run(model.bind_tools([]).ainvoke([("user", "hi")])).content == "from backup"


def test_no_backup_model_gives_a_clear_error():
    with pytest.raises(LLMUnavailable):
        asyncio.run(FallbackModel(BrokenModel(), None, "").ainvoke([("user", "hi")]))


def test_slow_tool_chaos_causes_a_timeout():
    async def run(args, role):
        return "ok"

    registry = ToolRegistry([AgentTool("get_service", "x", {"type": "object"}, run)], timeout_s=0.05,
                            chaos_delay_s=0.2)

    assert asyncio.run(registry.execute("get_service", {}, Role.ANALYST)).status == "timeout"


def test_fake_citation_chaos_is_caught_by_the_validator(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "chaos_fake_citation", True)
    graph = build_graph(FakeLLM(), FakeSearcher([0.9]))
    context = RuntimeContext(user_id="viewer", role=Role.VIEWER, name="Test User")

    result = asyncio.run(graph.ainvoke({"messages": [HumanMessage("password policy?")]}, context=context))

    assert result["attempts"] == 2
    assert result["messages"][-1].content == GOOD_ANSWER
    assert prompts.UNVERIFIED != result["messages"][-1].content


def test_health_reports_assistant_and_chaos(client):
    body = client.get("/health").json()

    assert body["assistant"] == "not configured"
    assert body["chaos"] == []
    assert "strong" in body["models"]
