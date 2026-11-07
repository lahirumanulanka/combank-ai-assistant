from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from app.core.rbac import Role, allowed_access_levels

DocumentType = Literal["incident", "architecture", "runbook", "spec", "policy", "meeting_notes", "hr", "faq"]
Department = Literal["payments", "platform", "security", "operations", "product", "hr", "general"]
AccessLevel = Literal["public", "internal", "confidential", "restricted"]


class InvalidDocument(Exception):
    pass


class DocumentMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    document_type: DocumentType
    department: Department
    access_level: AccessLevel
    created_date: date
    service: str = "n/a"
    severity: str = "n/a"
    owner_team: str
    tags: list[str]


class Document(BaseModel):
    meta: DocumentMeta
    body: str
    path: str


def split_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise InvalidDocument("file must start with a '---' front-matter block")

    _, front_matter, body = text.split("---\n", 2)
    return yaml.safe_load(front_matter), body.strip()


def load_document(path: Path) -> Document:
    try:
        meta, body = split_front_matter(path.read_text())
        return Document(meta=DocumentMeta(**meta), body=body, path=str(path))
    except (ValueError, TypeError, yaml.YAMLError, InvalidDocument) as exc:
        raise InvalidDocument(f"{path}: {exc}") from exc


def load_documents(folder: Path) -> list[Document]:
    return [load_document(path) for path in sorted(folder.rglob("*.md"))]


def visible_to(documents: list[Document], role: Role) -> list[Document]:
    allowed = allowed_access_levels(role)
    return [doc for doc in documents if doc.meta.access_level in allowed]
