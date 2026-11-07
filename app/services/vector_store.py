from pinecone import Pinecone, ServerlessSpec

from app.core.config import Settings, require_secret
from app.core.logging import get_logger

log = get_logger(__name__)


class VectorStore:
    def __init__(self, api_key: str, index_name: str, dimension: int, cloud: str, region: str):
        self._client = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.dimension = dimension
        self.cloud = cloud
        self.region = region
        self._index = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "VectorStore":
        api_key = require_secret(settings.pinecone_api_key, "PINECONE_API_KEY")
        return cls(
            api_key,
            settings.pinecone_index,
            settings.embedding_dimension,
            settings.pinecone_cloud,
            settings.pinecone_region,
        )

    def ensure_index(self) -> None:
        if self._client.has_index(self.index_name):
            return
        log.info("creating_index", index=self.index_name, dimension=self.dimension)
        self._client.create_index(
            name=self.index_name,
            dimension=self.dimension,
            metric="dotproduct",
            spec=ServerlessSpec(cloud=self.cloud, region=self.region),
        )

    @property
    def index(self):
        if self._index is None:
            self._index = self._client.Index(self.index_name)
        return self._index

    def upsert(self, records: list[dict], namespace: str, batch_size: int = 100) -> None:
        for start in range(0, len(records), batch_size):
            self.index.upsert(vectors=records[start:start + batch_size], namespace=namespace)

    def stats(self) -> dict:
        stats = self.index.describe_index_stats()
        return {
            "total": stats.total_vector_count,
            "namespaces": {name: ns.vector_count for name, ns in stats.namespaces.items()},
        }
