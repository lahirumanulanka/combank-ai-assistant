import re

from pydantic import BaseModel

CITATION_PATTERN = re.compile(r"\[([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*#\d+)\]")


class CitationCheck(BaseModel):
    ok: bool
    cited: list[str]
    unknown: list[str]
    reason: str = ""


def find_citations(text: str) -> list[str]:
    return list(dict.fromkeys(CITATION_PATTERN.findall(text)))


def check_citations(answer: str, retrieved_ids: list[str], require: bool = True) -> CitationCheck:
    cited = find_citations(answer)
    unknown = [chunk_id for chunk_id in cited if chunk_id not in set(retrieved_ids)]

    if unknown:
        return CitationCheck(ok=False, cited=cited, unknown=unknown,
                             reason=f"These citations were not in the passages: {', '.join(unknown)}")
    if require and not cited:
        return CitationCheck(ok=False, cited=[], unknown=[], reason="The answer has no citations.")
    return CitationCheck(ok=True, cited=cited, unknown=[])
