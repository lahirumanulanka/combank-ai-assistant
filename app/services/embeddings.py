from openai import AsyncOpenAI

from app.core.config import Settings, require_secret


class EmbeddingService:
    def __init__(self, api_key: str, model: str, dimension: int):
        self._client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimension = dimension

    @classmethod
    def from_settings(cls, settings: Settings) -> "EmbeddingService":
        api_key = require_secret(settings.openai_api_key, "OPENAI_API_KEY")
        return cls(api_key, settings.embedding_model, settings.embedding_dimension)

    async def embed(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            response = await self._client.embeddings.create(model=self.model, input=batch)
            vectors.extend(item.embedding for item in response.data)
        return vectors

    async def embed_one(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]
