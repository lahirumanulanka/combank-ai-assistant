from langgraph.runtime import Runtime

from app.core.config import get_settings
from app.core.logging import get_logger
from app.graph.context import RuntimeContext
from app.graph.state import AgentState
from app.guards.injection import guard_passages

log = get_logger(__name__)


def make_retrieval(searcher):
    async def retrieval(state: AgentState, runtime: Runtime[RuntimeContext]) -> dict:
        min_score = get_settings().retrieval_min_score
        results = await searcher.search(state["search_query"], runtime.context.role)
        degraded = any(result.source == "local_bm25" for result in results)
        strong = [result.model_dump() for result in results if degraded or result.score >= min_score]
        kept, dropped = guard_passages(strong)

        if dropped:
            log.warning("retrieved_injection_dropped", chunks=dropped)
        log.info("retrieval_done", found=len(results), kept=len(kept), min_score=min_score, degraded=degraded)
        return {"retrieved": kept, "dropped": dropped, "degraded": degraded}

    return retrieval
