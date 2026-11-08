from pathlib import Path

from langgraph.graph import END, START, StateGraph

from app.core.config import get_settings
from app.graph.context import RuntimeContext
from app.graph.nodes.input_guard import blocked_response, input_guard, route_after_guard
from app.graph.nodes.research import (
    fan_out_to_workers,
    make_research_execute,
    make_research_plan,
    make_research_worker,
    research_aggregate,
)
from app.graph.nodes.response import make_response
from app.graph.nodes.retrieval import make_retrieval
from app.graph.nodes.supervisor import make_supervisor, route_after_supervisor
from app.graph.nodes.tools import (
    make_tool_agent,
    make_tool_executor,
    route_after_tool_agent,
)
from app.graph.nodes.validator import route_after_validation, validator
from app.graph.state import AgentState
from app.knowledge.catalog import Library
from app.services.llm import create_resilient_model
from app.services.local_search import LocalSearch
from app.services.resilience import CircuitBreaker
from app.services.resilient_search import ResilientSearch
from app.services.search import get_hybrid_search
from app.tools.factory import build_tool_registry
from app.tools.knowledge_search import make_knowledge_search
from app.tools.python_analysis import make_python_analysis
from app.tools.registry import ToolRegistry


def build_graph(llm, searcher, checkpointer=None, library: Library | None = None, worker_llm=None,
                registry: ToolRegistry | None = None):
    library = library or Library([])
    worker_llm = worker_llm or llm
    registry = registry or ToolRegistry([make_knowledge_search(searcher), make_python_analysis(library)])
    graph = StateGraph(AgentState, context_schema=RuntimeContext)

    graph.add_node("input_guard", input_guard)
    graph.add_node("blocked_response", blocked_response)
    graph.add_node("supervisor", make_supervisor(llm))
    graph.add_node("retrieval", make_retrieval(searcher))
    graph.add_node("research_plan", make_research_plan(llm, library))
    graph.add_node("research_execute", make_research_execute(library))
    graph.add_node("research_worker", make_research_worker(worker_llm, library))
    graph.add_node("research_aggregate", research_aggregate)
    graph.add_node("tool_agent", make_tool_agent(llm, registry))
    graph.add_node("tool_executor", make_tool_executor(registry))
    graph.add_node("response", make_response(llm))
    graph.add_node("validator", validator)

    graph.add_edge(START, "input_guard")
    graph.add_conditional_edges("input_guard", route_after_guard, ["blocked_response", "supervisor"])
    graph.add_edge("blocked_response", END)
    graph.add_conditional_edges("supervisor", route_after_supervisor,
                                ["retrieval", "research_plan", "tool_agent", "response"])
    graph.add_edge("retrieval", "response")

    graph.add_edge("research_plan", "research_execute")
    graph.add_conditional_edges("research_execute", fan_out_to_workers, ["research_worker", "research_aggregate"])
    graph.add_edge("research_worker", "research_aggregate")
    graph.add_edge("research_aggregate", "response")

    graph.add_conditional_edges("tool_agent", route_after_tool_agent, ["tool_executor", "validator"])
    graph.add_edge("tool_executor", "tool_agent")

    graph.add_edge("response", "validator")
    graph.add_conditional_edges("validator", route_after_validation,
                                {"response": "response", "tool_agent": "tool_agent", "done": END})

    return graph.compile(checkpointer=checkpointer)


def build_resilient_search(settings, library: Library) -> ResilientSearch:
    return ResilientSearch(
        primary=get_hybrid_search(),
        local=LocalSearch.from_library(library),
        breaker=CircuitBreaker(settings.breaker_failures, settings.breaker_cooldown_s),
        timeout_s=settings.pinecone_timeout_s,
        chaos=settings.chaos_pinecone_fail,
    )


async def build_default_graph(checkpointer=None):
    settings = get_settings()
    library = Library.from_folder(Path(settings.docs_dir))
    searcher = build_resilient_search(settings, library)
    return build_graph(
        llm=create_resilient_model(settings.llm_strong, settings),
        searcher=searcher,
        checkpointer=checkpointer,
        library=library,
        worker_llm=create_resilient_model(settings.llm_cheap, settings),
        registry=await build_tool_registry(settings, searcher, library),
    )
