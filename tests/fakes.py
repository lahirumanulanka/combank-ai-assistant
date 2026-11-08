import re

from langchain_core.messages import AIMessage

from app.core.rbac import Role
from app.graph.nodes.research import BatchFindings, IncidentFinding, ResearchPlan
from app.graph.nodes.supervisor import RoutePlan
from app.services.search import SearchResult

GOOD_ANSWER = "Passwords rotate every 90 days [POL-SEC-001#4]."
DEFAULT_RESEARCH_PLAN = (
    'rows = catalog.filter(document_type="incident", tag="payments", since="2025-11-07")\n'
    "batches = batch(rows, size=2)"
)


class FakeStructured:
    def __init__(self, respond):
        self.respond = respond

    async def ainvoke(self, messages):
        return self.respond(messages)


class FakeLLM:
    def __init__(self, route: str = "qa", answer: str = GOOD_ANSWER, answers: list[str] | None = None,
                 plan_code: str = DEFAULT_RESEARCH_PLAN, causes: dict[str, str] | None = None,
                 fail_on: set[str] | None = None, irrelevant: set[str] | None = None,
                 tool_script: list[list[dict]] | None = None):
        self.plan = RoutePlan(route=route, search_query="password rotation policy", rationale="policy question")
        self.plan_code = plan_code
        self.causes = causes or {}
        self.fail_on = fail_on or set()
        self.irrelevant = irrelevant or set()
        self.answers = answers or [answer]
        self.system_prompts: list[str] = []
        self.worker_batches: list[list[str]] = []
        self.tool_script = tool_script or []
        self.bound_tools: list[list[str]] = []

    def with_structured_output(self, schema):
        if schema is ResearchPlan:
            return FakeStructured(lambda _: ResearchPlan(code=self.plan_code, rationale="payment incidents"))
        if schema is BatchFindings:
            return FakeStructured(self._find)
        return FakeStructured(lambda _: self.plan)

    def _find(self, messages) -> BatchFindings:
        ids = re.findall(r"^### (\S+)", messages[0][1], flags=re.MULTILINE)
        self.worker_batches.append(ids)
        if self.fail_on & set(ids):
            raise RuntimeError("worker model is down")
        return BatchFindings(findings=[
            IncidentFinding(incident_id=doc_id, root_cause_category=self.causes.get(doc_id, "other"),
                            summary=f"{doc_id} failed", fix="fix it", relevant=doc_id not in self.irrelevant)
            for doc_id in ids
        ])

    def bind_tools(self, specs: list[dict]):
        self.bound_tools.append([spec["function"]["name"] for spec in specs])
        return FakeToolModel(self)

    async def ainvoke(self, messages):
        self.system_prompts.append(messages[0][1])
        index = min(len(self.system_prompts) - 1, len(self.answers) - 1)
        return AIMessage(self.answers[index])


class FakeSearcher:
    def __init__(self, scores: list[float]):
        self.scores = scores
        self.calls: list[tuple[str, Role]] = []

    async def search(self, query: str, role: Role, **filters):
        self.calls.append((query, role))
        return [
            SearchResult(chunk_id=f"POL-SEC-001#{i}", doc_id="POL-SEC-001", title="Information Security Policy",
                         section="4. Authentication", text="rotate every 90 days", score=score,
                         namespace="security", access_level="internal")
            for i, score in enumerate(self.scores, start=4)
        ]


class FakeToolModel:
    def __init__(self, llm: FakeLLM):
        self.llm = llm

    async def ainvoke(self, messages):
        round_index = len(self.llm.bound_tools) - 1
        if round_index < len(self.llm.tool_script):
            calls = [{"name": c["name"], "args": c["args"], "id": f"call_{round_index}_{i}"}
                     for i, c in enumerate(self.llm.tool_script[round_index])]
            return AIMessage(content="", tool_calls=calls)
        return await self.llm.ainvoke(messages)
