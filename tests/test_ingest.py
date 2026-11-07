from datetime import date

from app.knowledge.bm25 import BM25Encoder
from app.knowledge.chunking import chunk_documents
from app.knowledge.documents import Document, DocumentMeta
from scripts.ingest import build_records


def make_document(doc_id: str, department: str) -> Document:
    meta = DocumentMeta(
        doc_id=doc_id,
        title=f"Title {doc_id}",
        document_type="policy",
        department=department,
        access_level="internal",
        created_date=date(2026, 1, 1),
        owner_team="team",
        tags=["x"],
    )
    return Document(meta=meta, body="## Part one\nSome words here.\n## Part two\nMore words.", path="x.md")


def test_records_are_grouped_by_department_namespace():
    chunks = chunk_documents([make_document("POL-A", "security"), make_document("POL-B", "payments")])
    dense = [[0.1, 0.2] for _ in chunks]
    bm25 = BM25Encoder().fit([c.text for c in chunks])

    records = build_records(chunks, dense, bm25)

    assert set(records) == {"security", "payments"}
    assert [r["id"] for r in records["security"]] == ["POL-A#0", "POL-A#1"]


def test_each_record_has_dense_sparse_and_text_metadata():
    chunks = chunk_documents([make_document("POL-A", "security")])
    bm25 = BM25Encoder().fit([c.text for c in chunks])

    record = build_records(chunks, [[0.5, 0.5]] * len(chunks), bm25)["security"][0]

    assert record["values"] == [0.5, 0.5]
    assert record["sparse_values"]["indices"]
    assert record["metadata"]["access_level"] == "internal"
    assert record["metadata"]["text"].startswith("Title POL-A")
