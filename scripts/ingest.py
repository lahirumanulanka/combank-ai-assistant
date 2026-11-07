import asyncio
import time
from collections import defaultdict
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.knowledge.bm25 import BM25Encoder
from app.knowledge.chunking import Chunk, chunk_documents
from app.knowledge.documents import load_documents
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStore

log = get_logger("ingest")


def build_records(chunks: list[Chunk], dense: list[list[float]], bm25: BM25Encoder) -> dict[str, list[dict]]:
    by_namespace: dict[str, list[dict]] = defaultdict(list)
    for chunk, vector in zip(chunks, dense, strict=True):
        by_namespace[chunk.metadata["department"]].append(
            {
                "id": chunk.chunk_id,
                "values": vector,
                "sparse_values": bm25.encode_document(chunk.text),
                "metadata": {**chunk.metadata, "text": chunk.text},
            }
        )
    return dict(by_namespace)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    started = time.perf_counter()

    documents = load_documents(Path(settings.docs_dir))
    chunks = chunk_documents(documents)
    texts = [chunk.text for chunk in chunks]
    log.info("chunked", documents=len(documents), chunks=len(chunks))

    bm25 = BM25Encoder().fit(texts)
    bm25.save(Path(settings.bm25_params_path))
    log.info("bm25_fitted", vocabulary=len(bm25.doc_freq), saved_to=settings.bm25_params_path)

    dense = await EmbeddingService.from_settings(settings).embed(texts)
    log.info("embedded", vectors=len(dense), dimension=len(dense[0]))

    store = VectorStore.from_settings(settings)
    store.ensure_index()
    for namespace, records in build_records(chunks, dense, bm25).items():
        store.upsert(records, namespace=namespace)
        log.info("upserted", namespace=namespace, vectors=len(records))

    log.info("ingest_finished", seconds=round(time.perf_counter() - started, 1))


if __name__ == "__main__":
    asyncio.run(main())
