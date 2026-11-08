import json
from collections import Counter
from datetime import date
from typing import Literal

from langgraph.runtime import Runtime
from langgraph.types import Send
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.graph import prompts
from app.graph.context import RuntimeContext
from app.graph.state import AgentState, WorkerInput
from app.guards.injection import scan
from app.knowledge.catalog import Library
from app.knowledge.chunking import chunk_document
from app.knowledge.documents import Document
from app.knowledge.sandbox import PLAN_LANGUAGE, PlanRejected, run_plan

log = get_logger(__name__)

RootCause = Literal[
    "connection_pool_exhaustion", "expired_tls_certificate", "idempotency_cache_eviction",
    "config_drift_deployment", "key_rotation_failure", "disk_full", "quota_exhausted", "other",
]
EVIDENCE_SECTIONS = {"Impact", "Root cause", "Follow-up actions"}
FALLBACK_PLAN = 'rows = catalog.filter(document_type="incident", since=months_ago(12))\nbatches = batch(rows, size=4)'


class ResearchPlan(BaseModel):
    code: str = Field(max_length=1500)
    rationale: str = Field(max_length=300)


class IncidentFinding(BaseModel):
    incident_id: str
    root_cause_category: RootCause
    summary: str = Field(max_length=400)
    fix: str = Field(max_length=300)
    relevant: bool


class BatchFindings(BaseModel):
    findings: list[IncidentFinding]


def make_research_plan(llm, library: Library):
    planner = llm.with_structured_output(ResearchPlan)

    async def research_plan(state: AgentState, runtime: Runtime[RuntimeContext]) -> dict:
        view = library.view_for(runtime.context.role)
        system = prompts.RESEARCH_PLANNER.format(
            brand=get_settings().brand_name,
            language=PLAN_LANGUAGE,
            today=date.today().isoformat(),
            catalog=json.dumps(view.describe(), indent=1),
        )
        plan: ResearchPlan = await planner.ainvoke([("system", system), ("user", state["search_query"])])
        log.info("research_planned", rationale=plan.rationale)
        return {"plan_code": plan.code, "plan_rationale": plan.rationale}

    return research_plan


def make_research_execute(library: Library):
    async def research_execute(state: AgentState, runtime: Runtime[RuntimeContext]) -> dict:
        view = library.view_for(runtime.context.role)
        try:
            return {"batches": run_plan(state["plan_code"], view), "plan_source": "llm_plan"}
        except PlanRejected as exc:
            log.warning("plan_rejected", reason=str(exc))
            source = f"fallback plan (LLM plan rejected: {exc})"
        try:
            return {"batches": run_plan(FALLBACK_PLAN, view), "plan_source": source}
        except PlanRejected:
            return {"batches": [], "plan_source": source}

    return research_execute


def fan_out_to_workers(state: AgentState) -> list[Send] | str:
    if not state.get("batches"):
        return "research_aggregate"
    return [Send("research_worker", {"batch": group, "question": state["search_query"]}) for group in state["batches"]]


def format_evidence(documents: list[Document]) -> str:
    parts = []
    for doc in documents:
        sections = [chunk.text for chunk in chunk_document(doc)
                    if chunk.section in EVIDENCE_SECTIONS and not scan(chunk.text).flagged]
        meta = doc.meta
        body = "\n\n".join(sections)
        parts.append(f"### {meta.doc_id} ({meta.created_date}, {meta.service})\n<<doc id=\"{meta.doc_id}\">>\n{body}\n<</doc>>")
    return "\n\n".join(parts)


def root_cause_chunk_id(doc: Document) -> str:
    for chunk in chunk_document(doc):
        if chunk.section == "Root cause":
            return chunk.chunk_id
    return f"{doc.meta.doc_id}#0"


def make_research_worker(llm, library: Library):
    extractor = llm.with_structured_output(BatchFindings)

    async def research_worker(task: WorkerInput, runtime: Runtime[RuntimeContext]) -> dict:
        role = runtime.context.role
        documents = [doc for doc in (library.get(doc_id, role) for doc_id in task["batch"]) if doc]
        system = prompts.RESEARCH_WORKER.format(brand=get_settings().brand_name,
                                                documents=format_evidence(documents)) + prompts.SPOTLIGHT_RULE
        try:
            result: BatchFindings = await extractor.ainvoke([("system", system), ("user", task["question"])])
        except Exception as exc:  # noqa: BLE001 - one failed worker must not stop the others
            log.warning("research_worker_failed", batch=task["batch"], error=type(exc).__name__)
            return {"research_errors": [f"{doc_id}: worker failed" for doc_id in task["batch"]]}

        by_id = {doc.meta.doc_id: doc for doc in documents}
        findings: dict[str, dict] = {}
        for found in result.findings:
            doc = by_id.get(found.incident_id)
            if doc and found.incident_id not in findings:
                findings[found.incident_id] = {
                    "incident_id": found.incident_id,
                    "date": doc.meta.created_date.isoformat(),
                    "service": doc.meta.service,
                    "root_cause_category": found.root_cause_category,
                    "summary": found.summary,
                    "fix": found.fix,
                    "relevant": found.relevant,
                    "chunk_id": root_cause_chunk_id(doc),
                }
        missing = [doc_id for doc_id in task["batch"] if doc_id not in findings]
        return {"findings": list(findings.values()), "research_errors": [f"{doc_id}: not analysed" for doc_id in missing]}

    return research_worker


async def research_aggregate(state: AgentState) -> dict:
    analysed = sorted(state.get("findings", []), key=lambda finding: finding["date"])
    findings = [finding for finding in analysed if finding["relevant"]]
    planned = sum(len(group) for group in state.get("batches", []))
    counts = Counter(finding["root_cause_category"] for finding in findings)

    analysis = {
        "coverage": f"{len(analysed)}/{planned}",
        "relevant": len(findings),
        "excluded": [finding["incident_id"] for finding in analysed if not finding["relevant"]],
        "period": f"{findings[0]['date']} to {findings[-1]['date']}" if findings else "n/a",
        "root_causes": [
            {
                "cause": cause,
                "count": count,
                "incidents": [f["incident_id"] for f in findings if f["root_cause_category"] == cause],
            }
            for cause, count in counts.most_common()
        ],
        "by_month": dict(sorted(Counter(finding["date"][:7] for finding in findings).items())),
        "not_analysed": state.get("research_errors", []),
    }
    retrieved = [
        {
            "chunk_id": f["chunk_id"],
            "title": f["incident_id"],
            "section": f"{f['date']} | {f['service']} | {f['root_cause_category']}",
            "text": f"{f['summary']} Fix: {f['fix']}",
        }
        for f in findings
    ]
    log.info("research_aggregated", coverage=analysis["coverage"], causes=dict(counts))
    return {"analysis": analysis, "retrieved": retrieved}
