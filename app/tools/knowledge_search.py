from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.rbac import Role
from app.knowledge.documents import DocumentType
from app.tools.registry import AgentTool


class KnowledgeSearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=300, description="What to look for in the bank's documents")
    document_type: DocumentType | None = Field(default=None, description="Optional document type filter")


def make_knowledge_search(searcher) -> AgentTool:
    async def run(args: dict, role: Role) -> list[dict]:
        parsed = KnowledgeSearchArgs.model_validate(args)
        results = await searcher.search(parsed.query, role, document_type=parsed.document_type)
        min_score = get_settings().retrieval_min_score
        return [
            {"chunk_id": r.chunk_id, "title": r.title, "section": r.section, "text": r.text}
            for r in results if r.score >= min_score
        ]

    return AgentTool(
        name="knowledge_search",
        description="Search Commercial Bank's documents (policies, incidents, runbooks, architecture, specs). "
                    "Returns passages with citation ids like POL-SEC-001#4.",
        parameters=KnowledgeSearchArgs.model_json_schema(),
        run=run,
    )
