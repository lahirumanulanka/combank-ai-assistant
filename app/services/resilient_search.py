import asyncio

from app.core.logging import get_logger
from app.core.rbac import Role
from app.services.local_search import LocalSearch
from app.services.resilience import CircuitBreaker
from app.services.search import SearchResult

log = get_logger(__name__)


class ResilientSearch:
    def __init__(self, primary, local: LocalSearch, breaker: CircuitBreaker, timeout_s: float, chaos: bool = False):
        self._primary = primary
        self._local = local
        self._breaker = breaker
        self._timeout_s = timeout_s
        self._chaos = chaos

    async def search(self, query: str, role: Role, document_type: str | None = None, **filters) -> list[SearchResult]:
        if self._breaker.is_open():
            log.warning("vector_db_circuit_open", fallback="local_bm25")
        else:
            try:
                if self._chaos:
                    raise ConnectionError("chaos: Pinecone is down")
                results = await asyncio.wait_for(
                    self._primary.search(query, role, document_type=document_type, **filters), self._timeout_s
                )
                self._breaker.record_success()
                return results
            except Exception as exc:  # noqa: BLE001 - any vector DB problem falls back to local search
                self._breaker.record_failure()
                log.warning("vector_db_failed", error=type(exc).__name__, fallback="local_bm25")

        return self._local.search(query, role, document_type=document_type)
