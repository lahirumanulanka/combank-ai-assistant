from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.rbac import Role
from app.knowledge.catalog import Library, Row
from app.knowledge.documents import DocumentType
from app.tools.registry import AgentTool

GroupField = Literal["service", "severity", "department", "month"]


class AnalysisArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["count_by", "timeline", "list"] = Field(
        description="count_by: count documents per field; timeline: count per month; list: show matching documents"
    )
    field: GroupField | None = Field(default=None, description="Field to group by (needed for count_by)")
    document_type: DocumentType = "incident"
    service: str | None = Field(default=None, description="e.g. payment-gateway")
    severity: Literal["SEV1", "SEV2", "SEV3", "SEV4"] | None = None
    tag: str | None = Field(default=None, description="e.g. payments")
    since: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")


def group_value(row: Row, field: GroupField) -> str:
    return row.date[:7] if field == "month" else getattr(row, field)


def analyse(rows: list[Row], args: AnalysisArgs) -> dict:
    rows = [row for row in rows if args.severity is None or row.severity == args.severity]

    if args.operation == "list":
        result = [{"doc_id": r.doc_id, "date": r.date, "service": r.service, "severity": r.severity, "title": r.title}
                  for r in sorted(rows, key=lambda row: row.date)]
    else:
        field = "month" if args.operation == "timeline" else (args.field or "service")
        counts = Counter(group_value(row, field) for row in rows)
        ordered = sorted(counts.items()) if field == "month" else counts.most_common()
        result = [{field: value, "count": count} for value, count in ordered]

    return {"operation": args.operation, "rows_used": len(rows), "result": result,
            "source_documents": [row.doc_id for row in rows]}


def no_match_hint(rows: list[Row]) -> dict:
    return {
        "hint": "No documents matched. Use an exact service name, or tag= for a topic such as payments.",
        "services": sorted({row.service for row in rows} - {"n/a"}),
        "tags": sorted({tag for row in rows for tag in row.tags}),
    }


def make_python_analysis(library: Library) -> AgentTool:
    async def run(args: dict, role: Role) -> dict:
        parsed = AnalysisArgs.model_validate(args)
        view = library.view_for(role)
        rows = view.filter(document_type=parsed.document_type, service=parsed.service, tag=parsed.tag,
                           since=parsed.since)
        result = analyse(rows, parsed)
        if not result["rows_used"]:
            result |= no_match_hint(view.filter(document_type=parsed.document_type))
        return result

    services = ", ".join(sorted({doc.meta.service for doc in library.documents} - {"n/a"}))

    return AgentTool(
        name="python_analysis",
        description="Structured analysis over the bank's documents the user may see (incidents by default): "
                    "count by service, severity, department or month, a monthly timeline, or a filtered list. "
                    "Use it for questions about counts, trends or comparisons. For a topic such as payments use "
                    f"tag='payments'. service must be an exact name: {services}.",
        parameters=AnalysisArgs.model_json_schema(),
        run=run,
    )
