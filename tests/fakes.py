from langchain_core.messages import AIMessage

from app.core.rbac import Role
from app.graph.nodes.supervisor import RoutePlan
from app.services.search import SearchResult


class FakePlanner:
    def __init__(self, plan: RoutePlan):
        self.plan = plan

    async def ainvoke(self, messages):
        return self.plan


GOOD_ANSWER = "Passwords rotate every 90 days [POL-SEC-001#4]."


class FakeLLM:
    def __init__(self, route: str = "qa", answer: str = GOOD_ANSWER, answers: list[str] | None = None):
        self.plan = RoutePlan(route=route, search_query="password rotation policy", rationale="policy question")
        self.answers = answers or [answer]
        self.system_prompts: list[str] = []

    def with_structured_output(self, schema):
        return FakePlanner(self.plan)

    async def ainvoke(self, messages):
        self.system_prompts.append(messages[0][1])
        index = min(len(self.system_prompts) - 1, len(self.answers) - 1)
        return AIMessage(self.answers[index])


class FakeSearcher:
    def __init__(self, scores: list[float]):
        self.scores = scores
        self.calls: list[tuple[str, Role]] = []

    async def search(self, query: str, role: Role):
        self.calls.append((query, role))
        return [
            SearchResult(chunk_id=f"POL-SEC-001#{i}", doc_id="POL-SEC-001", title="Information Security Policy",
                         section="4. Authentication", text="rotate every 90 days", score=score,
                         namespace="security", access_level="internal")
            for i, score in enumerate(self.scores, start=4)
        ]
