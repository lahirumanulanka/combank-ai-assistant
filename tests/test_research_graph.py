import asyncio

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.core.rbac import Role
from app.graph.builder import build_graph
from app.graph.context import RuntimeContext
from app.knowledge.catalog import Library
from scripts.generate_incidents import INCIDENTS
from scripts.generate_incidents import main as generate_incidents
from tests.fakes import FakeLLM, FakeSearcher

TRUE_CAUSES = {incident.doc_id: incident.root_cause for incident in INCIDENTS}
RESEARCH_ANSWER = "Connection pool exhaustion caused 4 incidents [INC-2026-03-14#3]."
QUESTION = "Summarize all payment outages last year and find recurring root causes."


@pytest.fixture(scope="module")
def library(tmp_path_factory) -> Library:
    folder = tmp_path_factory.mktemp("data")
    generate_incidents(folder)
    return Library.from_folder(folder / "docs")


def research_llm(**kwargs) -> FakeLLM:
    llm = FakeLLM(route="research", answer=RESEARCH_ANSWER, causes=TRUE_CAUSES, **kwargs)
    llm.plan.search_query = QUESTION
    return llm


def run(llm, library, role=Role.ANALYST, searcher=None, checkpointer=None, turns=1) -> dict:
    graph = build_graph(llm, searcher or FakeSearcher([0.9]), checkpointer=checkpointer, library=library)
    context = RuntimeContext(user_id=role.value, role=role, name="Test User")
    config = {"configurable": {"thread_id": "research-test"}}

    async def go():
        result = None
        for _ in range(turns):
            result = await graph.ainvoke({"messages": [HumanMessage(QUESTION)]}, config=config, context=context)
        return result

    return asyncio.run(go())


def test_analyst_research_finds_the_four_recurring_root_causes(library):
    result = run(research_llm(), library)

    counts = {item["cause"]: item["count"] for item in result["analysis"]["root_causes"]}
    assert counts == {
        "connection_pool_exhaustion": 4,
        "expired_tls_certificate": 3,
        "idempotency_cache_eviction": 3,
        "config_drift_deployment": 2,
    }
    assert result["analysis"]["coverage"] == "12/12"
    assert result["messages"][-1].content == RESEARCH_ANSWER


def test_plan_splits_work_into_parallel_batches(library):
    llm = research_llm()

    result = run(llm, library)

    assert result["plan_source"] == "llm_plan"
    assert len(result["batches"]) == 6
    assert sorted(llm.worker_batches) == sorted(result["batches"])
    assert "INC-2025-09-30" not in {doc_id for group in result["batches"] for doc_id in group}


def test_findings_are_citable_root_cause_chunks(library):
    result = run(research_llm(), library)

    assert "INC-2026-03-14#3" in [chunk["chunk_id"] for chunk in result["retrieved"]]
    assert result["validation"]["ok"]


def test_viewer_is_downgraded_to_normal_search(library):
    llm, searcher = research_llm(), FakeSearcher([0.9])

    result = run(llm, library, role=Role.VIEWER, searcher=searcher)

    assert result["route"] == "qa"
    assert searcher.calls
    assert llm.worker_batches == []
    assert "analyst role" in llm.system_prompts[-1]


def test_rejected_plan_falls_back_to_a_safe_default(library):
    result = run(research_llm(plan_code="import os\nbatches = []"), library)

    assert result["plan_source"].startswith("fallback plan")
    assert result["batches"]


def test_one_failed_worker_is_reported_and_the_rest_continue(library):
    result = run(research_llm(fail_on={"INC-2026-03-14"}), library)

    analysis = result["analysis"]
    assert analysis["coverage"] == "10/12"
    assert len(analysis["not_analysed"]) == 2
    assert any("INC-2026-03-14" in error for error in analysis["not_analysed"])


def test_findings_do_not_pile_up_across_turns(library):
    result = run(research_llm(), library, checkpointer=InMemorySaver(), turns=2)

    assert len(result["findings"]) == 12


def test_workers_drop_documents_that_do_not_fit_the_question(library):
    plan = 'rows = catalog.filter(document_type="incident", since="2025-11-07")\nbatches = batch(rows, size=4)'

    result = run(research_llm(plan_code=plan, irrelevant={"INC-2026-02-27", "INC-2026-05-05", "INC-2026-10-08"}),
                 library)

    analysis = result["analysis"]
    assert analysis["excluded"] == ["INC-2026-02-27", "INC-2026-05-05", "INC-2026-10-08"]
    assert analysis["relevant"] == 12
    assert {c["cause"]: c["count"] for c in analysis["root_causes"]}["connection_pool_exhaustion"] == 4
