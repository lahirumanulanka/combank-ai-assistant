from datetime import date
from pathlib import Path

import pytest

from app.knowledge.chunking import (
    MAX_WORDS,
    OVERLAP_WORDS,
    chunk_document,
    chunk_documents,
    split_long_text,
    split_sections,
)
from app.knowledge.documents import Document, DocumentMeta, load_documents

BODY = """> FICTIONAL MOCK DATA generated for a technical assessment.

# Password Policy

**Policy ID:** POL-X

## Rotation
Passwords rotate every 90 days.

## Exceptions
The CISO approves exceptions.
"""


def make_document(body: str = BODY) -> Document:
    meta = DocumentMeta(
        doc_id="POL-X",
        title="Password Policy",
        document_type="policy",
        department="security",
        access_level="internal",
        created_date=date(2026, 1, 1),
        owner_team="security",
        tags=["password"],
    )
    return Document(meta=meta, body=body, path="POL-X.md")


def test_sections_follow_the_headings_and_skip_the_banner():
    sections = split_sections(BODY)

    assert [heading for heading, _ in sections] == ["Overview", "Rotation", "Exceptions"]
    assert all("FICTIONAL" not in content for _, content in sections)


def test_chunk_ids_are_doc_id_and_position():
    chunks = chunk_document(make_document())

    assert [c.chunk_id for c in chunks] == ["POL-X#0", "POL-X#1", "POL-X#2"]


def test_every_chunk_starts_with_title_and_section():
    chunk = chunk_document(make_document())[1]

    assert chunk.text.startswith("Password Policy\n## Rotation\n")
    assert "90 days" in chunk.text


def test_chunk_metadata_carries_the_access_level_for_rbac():
    chunk = chunk_document(make_document())[0]

    assert chunk.metadata["access_level"] == "internal"
    assert chunk.metadata["department"] == "security"
    assert chunk.metadata["created_date"] == "2026-01-01"
    assert chunk.metadata["section"] == "Overview"


def test_short_text_stays_in_one_piece():
    assert split_long_text("a few words only") == ["a few words only"]


def test_long_text_is_split_with_overlap():
    words = [f"w{i}" for i in range(600)]

    pieces = split_long_text(" ".join(words))

    assert len(pieces) == 3
    assert all(len(piece.split()) <= MAX_WORDS for piece in pieces)
    first_end = pieces[0].split()[-OVERLAP_WORDS:]
    second_start = pieces[1].split()[:OVERLAP_WORDS]
    assert first_end == second_start
    assert pieces[-1].split()[-1] == "w599"


def test_real_corpus_chunk_ids_are_unique():
    docs_dir = Path("data/docs")
    if not docs_dir.exists():
        pytest.skip("data/docs not present")

    chunks = chunk_documents(load_documents(docs_dir))
    ids = [c.chunk_id for c in chunks]

    assert len(ids) == len(set(ids))
