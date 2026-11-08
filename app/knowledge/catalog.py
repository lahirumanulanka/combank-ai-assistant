from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.core.rbac import Role, allowed_access_levels
from app.knowledge.documents import Document, load_documents


@dataclass(frozen=True)
class Row:
    doc_id: str
    title: str
    document_type: str
    department: str
    service: str
    date: str
    tags: tuple[str, ...]


class CatalogView:
    def __init__(self, rows: list[Row]):
        self._rows = rows

    def filter(self, document_type: str | None = None, department: str | None = None,
               service: str | None = None, tag: str | None = None, since: str | None = None) -> list[Row]:
        return [
            row for row in self._rows
            if (document_type is None or row.document_type == document_type)
            and (department is None or row.department == department)
            and (service is None or row.service == service)
            and (tag is None or tag in row.tags)
            and (since is None or row.date >= since)
        ]

    def search(self, text: str, since: str | None = None) -> list[Row]:
        text = text.lower()
        return [
            row for row in self._rows
            if (text in row.title.lower() or any(text in tag for tag in row.tags))
            and (since is None or row.date >= since)
        ]

    def ids(self) -> set[str]:
        return {row.doc_id for row in self._rows}

    def describe(self) -> dict:
        return {
            "documents": len(self._rows),
            "types": dict(Counter(row.document_type for row in self._rows)),
            "departments": dict(Counter(row.department for row in self._rows)),
            "services": sorted({row.service for row in self._rows} - {"n/a"}),
            "tags": sorted({tag for row in self._rows for tag in row.tags}),
            "dates": f"{min(row.date for row in self._rows)} to {max(row.date for row in self._rows)}"
            if self._rows else "n/a",
        }


class Library:
    def __init__(self, documents: list[Document]):
        self._documents = {doc.meta.doc_id: doc for doc in documents}

    @classmethod
    def from_folder(cls, folder: Path) -> "Library":
        return cls(load_documents(folder))

    def view_for(self, role: Role) -> CatalogView:
        allowed = allowed_access_levels(role)
        return CatalogView([_to_row(doc) for doc in self._documents.values() if doc.meta.access_level in allowed])

    def get(self, doc_id: str, role: Role) -> Document | None:
        doc = self._documents.get(doc_id)
        if doc is None or doc.meta.access_level not in allowed_access_levels(role):
            return None
        return doc


def _to_row(doc: Document) -> Row:
    meta = doc.meta
    return Row(meta.doc_id, meta.title, meta.document_type, meta.department, meta.service,
               meta.created_date.isoformat(), tuple(meta.tags))


def months_ago(months: int, today: date | None = None) -> str:
    today = today or date.today()
    month_index = today.year * 12 + today.month - 1 - months
    year, month = divmod(month_index, 12)
    return date(year, month + 1, min(today.day, 28)).isoformat()
