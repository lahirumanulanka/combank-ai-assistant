from langgraph.runtime import Runtime

from app.core.config import get_settings
from app.core.logging import get_logger
from app.graph.context import RuntimeContext
from app.graph.state import AgentState

log = get_logger(__name__)


def make_retrieval(searcher):
    async def retrieval(state: AgentState, runtime: Runtime[RuntimeContext]) -> dict:
        min_score = get_settings().retrieval_min_score
        results = await searcher.search(state["search_query"], runtime.context.role)
        kept = [result for result in results if result.score >= min_score]

        log.info("retrieval_done", found=len(results), kept=len(kept), min_score=min_score)
        return {"retrieved": [result.model_dump() for result in kept]}

    return retrieval
