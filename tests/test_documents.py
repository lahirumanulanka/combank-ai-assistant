from pathlib import Path

import pytest

from app.core.rbac import Role
from app.knowledge.documents import (
    InvalidDocument,
    load_document,
    load_documents,
    visible_to,
)

DOCS_DIR = Path("data/docs")


@pytest.fixture(scope="module")
def documents():
    if not DOCS_DIR.exists():
        pytest.skip("data/docs is not in git; add the mock documents locally to run corpus tests")
    return load_documents(DOCS_DIR)


def test_all_mock_documents_load(documents):
    assert len(documents) >= 11


def test_doc_ids_are_unique_and_match_file_names(documents):
    ids = [doc.meta.doc_id for doc in documents]

    assert len(ids) == len(set(ids))
    for doc in documents:
        assert Path(doc.path).stem == doc.meta.doc_id


def test_documents_live_in_the_folder_of_their_type(documents):
    for doc in documents:
        assert Path(doc.path).parent.name == doc.meta.document_type


def test_every_document_has_the_fictional_banner(documents):
    for doc in documents:
        assert doc.body.startswith("> FICTIONAL MOCK DATA")


def test_each_role_sees_more_than_the_one_below(documents):
    viewer = visible_to(documents, Role.VIEWER)
    analyst = visible_to(documents, Role.ANALYST)
    admin = visible_to(documents, Role.ADMIN)

    assert len(viewer) < len(analyst) < len(admin) == len(documents)


def test_viewer_cannot_see_salary_bands(documents):
    viewer_ids = {doc.meta.doc_id for doc in visible_to(documents, Role.VIEWER)}
    analyst_ids = {doc.meta.doc_id for doc in visible_to(documents, Role.ANALYST)}

    assert "HR-COMP-001" not in viewer_ids
    assert "HR-COMP-001" not in analyst_ids
    assert "ARCH-IAM-001" not in viewer_ids
    assert "ARCH-IAM-001" in analyst_ids


def test_unknown_access_level_is_rejected(tmp_path):
    bad = tmp_path / "BAD-001.md"
    bad.write_text(
        "---\n"
        "doc_id: BAD-001\n"
        "title: Bad\n"
        "document_type: policy\n"
        "department: security\n"
        "access_level: top-secret\n"
        "created_date: '2026-01-01'\n"
        "owner_team: x\n"
        "tags: []\n"
        "---\n"
        "body\n"
    )

    with pytest.raises(InvalidDocument, match="BAD-001.md"):
        load_document(bad)


def test_file_without_front_matter_is_rejected(tmp_path):
    bad = tmp_path / "NOFM.md"
    bad.write_text("# Just a heading\n")

    with pytest.raises(InvalidDocument):
        load_document(bad)
