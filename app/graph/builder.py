from langgraph.graph import END, START, StateGraph

from app.core.config import get_settings
from app.graph.context import RuntimeContext
from app.graph.nodes.response import make_response
from app.graph.nodes.retrieval import make_retrieval
from app.graph.nodes.supervisor import make_supervisor, route_after_supervisor
from app.graph.state import AgentState
from app.services.llm import create_chat_model
from app.services.search import get_hybrid_search


def build_graph(llm, searcher, checkpointer=None):
    graph = StateGraph(AgentState, context_schema=RuntimeContext)

    graph.add_node("supervisor", make_supervisor(llm))
    graph.add_node("retrieval", make_retrieval(searcher))
    graph.add_node("response", make_response(llm))

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", route_after_supervisor, ["retrieval", "response"])
    graph.add_edge("retrieval", "response")
    graph.add_edge("response", END)

    return graph.compile(checkpointer=checkpointer)


def build_default_graph(checkpointer=None):
    settings = get_settings()
    llm = create_chat_model(settings.llm_strong, settings)
    return build_graph(llm, get_hybrid_search(), checkpointer)
