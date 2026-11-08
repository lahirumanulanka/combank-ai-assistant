from langsmith import traceable

from app.core.rbac import Role, allowed_access_levels
from app.core.tracing import as_documents, without_self
from app.knowledge.bm25 import BM25Encoder
from app.knowledge.catalog import Library
from app.knowledge.chunking import Chunk, chunk_documents
from app.services.search import SearchResult


class LocalSearch:
    """Keyword-only backup search over the chunks in memory, used when Pinecone is down."""

    def __init__(self, chunks: list[Chunk]):
        self._chunks = chunks
        self._bm25 = BM25Encoder().fit([chunk.text for chunk in chunks])
        self._weights = [self._to_dict(self._bm25.encode_document(chunk.text)) for chunk in chunks]

    @classmethod
    def from_library(cls, library: Library) -> "LocalSearch":
        return cls(chunk_documents(library.documents))

    @staticmethod
    def _to_dict(vector: dict) -> dict[int, float]:
        return dict(zip(vector["indices"], vector["values"], strict=True))

    @traceable(run_type="retriever", name="local_bm25_search", process_inputs=without_self, process_outputs=as_documents)
    def search(self, query: str, role: Role, top_k: int = 8, document_type: str | None = None) -> list[SearchResult]:
        query_weights = self._to_dict(self._bm25.encode_query(query))
        allowed = allowed_access_levels(role)

        scored = []
        for chunk, weights in zip(self._chunks, self._weights, strict=True):
            meta = chunk.metadata
            if meta["access_level"] not in allowed or (document_type and meta["document_type"] != document_type):
                continue
            score = sum(value * weights.get(index, 0.0) for index, value in query_weights.items())
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            SearchResult(chunk_id=chunk.chunk_id, doc_id=chunk.doc_id, title=str(chunk.metadata["title"]),
                         section=chunk.section, text=chunk.text, score=round(score, 4),
                         namespace=str(chunk.metadata["department"]), access_level=str(chunk.metadata["access_level"]),
                         source="local_bm25")
            for score, chunk in scored[:top_k]
        ]
