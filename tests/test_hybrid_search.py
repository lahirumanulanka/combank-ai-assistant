import asyncio
from datetime import date

import pytest

from app.core.rbac import Role
from app.knowledge.bm25 import BM25Encoder
from app.knowledge.hybrid import build_filter, scale_for_hybrid
from app.services.search import HybridSearch


class FakeEmbeddings:
    async def embed_one(self, text: str) -> list[float]:
        return [1.0, 1.0]


class FakeStore:
    def __init__(self, matches_by_namespace: dict[str, list[dict]]):
        self.matches_by_namespace = matches_by_namespace
        self.calls: list[dict] = []

    def query(self, dense, sparse, top_k, metadata_filter, namespace):
        self.calls.append({"dense": dense, "sparse": sparse, "filter": metadata_filter, "namespace": namespace})
        return self.matches_by_namespace.get(namespace, [])


def match(chunk_id: str, score: float) -> dict:
    doc_id = chunk_id.split("#")[0]
    metadata = {"doc_id": doc_id, "title": doc_id, "section": "S", "text": "t", "access_level": "internal"}
    return {"id": chunk_id, "score": score, "metadata": metadata}


def make_search(store: FakeStore) -> HybridSearch:
    bm25 = BM25Encoder().fit(["password rotation policy", "connection pool exhausted"])
    return HybridSearch(FakeEmbeddings(), store, bm25, default_alpha=0.7, default_top_k=3)


def test_alpha_one_keeps_only_meaning_search():
    dense, sparse = scale_for_hybrid([0.5, 0.5], {"indices": [7], "values": [2.0]}, alpha=1.0)

    assert dense == [0.5, 0.5]
    assert sparse["values"] == [0.0]


def test_alpha_zero_keeps_only_keyword_search():
    dense, sparse = scale_for_hybrid([0.5, 0.5], {"indices": [7], "values": [2.0]}, alpha=0.0)

    assert dense == [0.0, 0.0]
    assert sparse["values"] == [2.0]


def test_alpha_outside_zero_to_one_is_rejected():
    with pytest.raises(ValueError):
        scale_for_hybrid([1.0], {"indices": [], "values": []}, alpha=1.5)


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (Role.VIEWER, ["public", "internal"]),
        (Role.ANALYST, ["public", "internal", "confidential"]),
        (Role.ADMIN, ["public", "internal", "confidential", "restricted"]),
    ],
)
def test_filter_is_built_from_the_role(role, allowed):
    assert build_filter(role) == {"access_level": {"$in": allowed}}


def test_filter_can_narrow_by_type_and_date():
    metadata_filter = build_filter(Role.ANALYST, document_type="incident", since=date(2025, 11, 7))

    assert metadata_filter["document_type"] == {"$eq": "incident"}
    assert metadata_filter["created_on"] == {"$gte": 20251107}


def test_search_sends_the_role_filter_to_every_namespace():
    store = FakeStore({})

    asyncio.run(make_search(store).search("password", Role.VIEWER, namespaces=["security", "hr"]))

    assert [call["namespace"] for call in store.calls] == ["security", "hr"]
    for call in store.calls:
        assert call["filter"]["access_level"]["$in"] == ["public", "internal"]


def test_results_from_all_namespaces_are_merged_by_score():
    store = FakeStore({
        "security": [match("POL-SEC-001#4", 0.9), match("POL-SEC-001#1", 0.2)],
        "general": [match("POL-BRAND-001#2", 0.5)],
        "payments": [match("INC-2026-03-14#3", 0.7)],
    })

    results = asyncio.run(make_search(store).search("password", Role.VIEWER))

    assert [r.chunk_id for r in results] == ["POL-SEC-001#4", "INC-2026-03-14#3", "POL-BRAND-001#2"]
    assert results[0].namespace == "security"


def test_query_vectors_are_scaled_by_alpha():
    store = FakeStore({})

    asyncio.run(make_search(store).search("password", Role.ADMIN, namespaces=["security"], alpha=0.25))

    assert store.calls[0]["dense"] == [0.25, 0.25]
