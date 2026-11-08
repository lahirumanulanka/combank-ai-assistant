import asyncio
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import get_args

from langsmith import traceable
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.rbac import Role
from app.core.tracing import as_documents, without_self
from app.knowledge.bm25 import BM25Encoder
from app.knowledge.documents import Department
from app.knowledge.hybrid import build_filter, scale_for_hybrid
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStore

log = get_logger(__name__)

ALL_NAMESPACES: list[str] = list(get_args(Department))


class SearchResult(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str
    score: float
    namespace: str
    access_level: str
    source: str = "pinecone"


class HybridSearch:
    def __init__(self, embeddings: EmbeddingService, store: VectorStore, bm25: BM25Encoder,
                 default_alpha: float, default_top_k: int):
        self._embeddings = embeddings
        self._store = store
        self._bm25 = bm25
        self.default_alpha = default_alpha
        self.default_top_k = default_top_k

    @classmethod
    def from_settings(cls, settings: Settings) -> "HybridSearch":
        return cls(
            EmbeddingService.from_settings(settings),
            VectorStore.from_settings(settings),
            BM25Encoder.load(Path(settings.bm25_params_path)),
            settings.hybrid_alpha,
            settings.retrieval_top_k,
        )

    @traceable(run_type="retriever", name="pinecone_hybrid_search", process_inputs=without_self, process_outputs=as_documents)
    async def search(
        self,
        query: str,
        role: Role,
        namespaces: list[str] | None = None,
        top_k: int | None = None,
        alpha: float | None = None,
        document_type: str | None = None,
        since: date | None = None,
    ) -> list[SearchResult]:
        namespaces = namespaces or ALL_NAMESPACES
        top_k = top_k or self.default_top_k
        alpha = self.default_alpha if alpha is None else alpha

        dense = await self._embeddings.embed_one(query)
        sparse = self._bm25.encode_query(query)
        dense, sparse = scale_for_hybrid(dense, sparse, alpha)
        metadata_filter = build_filter(role, document_type, since)

        per_namespace = await asyncio.gather(
            *[
                asyncio.to_thread(self._store.query, dense, sparse, top_k, metadata_filter, namespace)
                for namespace in namespaces
            ]
        )

        results = [
            _to_result(match, namespace)
            for namespace, matches in zip(namespaces, per_namespace, strict=True)
            for match in matches
        ]
        results.sort(key=lambda result: result.score, reverse=True)
        results = results[:top_k]

        log.info("hybrid_search", role=role.value, alpha=alpha, namespaces=len(namespaces),
                 results=len(results), top=[r.chunk_id for r in results[:3]])
        return results


def _to_result(match: dict, namespace: str) -> SearchResult:
    metadata = match["metadata"]
    return SearchResult(
        chunk_id=match["id"],
        doc_id=metadata["doc_id"],
        title=metadata["title"],
        section=metadata["section"],
        text=metadata["text"],
        score=match["score"],
        namespace=namespace,
        access_level=metadata["access_level"],
    )


@lru_cache
def get_hybrid_search() -> HybridSearch:
    return HybridSearch.from_settings(get_settings())
