from datetime import date

from pydantic import BaseModel

from app.knowledge.documents import Document

MAX_WORDS = 250
OVERLAP_WORDS = 40
BANNER_PREFIX = "> FICTIONAL MOCK DATA"


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    section: str
    text: str
    metadata: dict[str, str | int | list[str]]


def split_sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading = "Overview"
    lines: list[str] = []

    for line in body.splitlines():
        if line.startswith((BANNER_PREFIX, "# ")):
            continue
        if line.startswith("## "):
            _add_section(sections, heading, lines)
            heading = line.removeprefix("## ").strip()
            lines = []
        else:
            lines.append(line)

    _add_section(sections, heading, lines)
    return sections


def _add_section(sections: list[tuple[str, str]], heading: str, lines: list[str]) -> None:
    content = "\n".join(lines).strip()
    if content:
        sections.append((heading, content))


def split_long_text(text: str, max_words: int = MAX_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]

    pieces = []
    step = max_words - overlap
    for start in range(0, len(words), step):
        pieces.append(" ".join(words[start:start + max_words]))
        if start + max_words >= len(words):
            break
    return pieces


def date_as_number(day: date) -> int:
    return int(day.strftime("%Y%m%d"))


def chunk_document(document: Document) -> list[Chunk]:
    meta = document.meta
    chunks: list[Chunk] = []

    for section, content in split_sections(document.body):
        for piece in split_long_text(content):
            index = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=f"{meta.doc_id}#{index}",
                    doc_id=meta.doc_id,
                    section=section,
                    text=f"{meta.title}\n## {section}\n{piece}",
                    metadata={
                        **meta.model_dump(mode="json"),
                        "created_on": date_as_number(meta.created_date),
                        "section": section,
                        "chunk_index": index,
                    },
                )
            )
    return chunks


def chunk_documents(documents: list[Document]) -> list[Chunk]:
    return [chunk for document in documents for chunk in chunk_document(document)]
