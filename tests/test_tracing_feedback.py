import os

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.tracing import configure_tracing
from app.graph.builder import build_graph
from tests.fakes import FakeLLM, FakeSearcher
from tests.helpers import parse_sse


@pytest.fixture
def clean_env(monkeypatch):
    for name in ["LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT", "LANGSMITH_ENDPOINT"]:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_tracing_stays_off_without_a_key(clean_env):
    settings = get_settings().model_copy(update={"langsmith_api_key": None})

    assert configure_tracing(settings) is False
    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert "LANGSMITH_API_KEY" not in os.environ


def test_tracing_turns_on_with_a_key(clean_env):
    settings = get_settings().model_copy(update={"langsmith_api_key": SecretStr("lsv2_test"),
                                                 "langsmith_project": "demo-project"})

    assert configure_tracing(settings) is True
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "demo-project"


class FakeLangSmith:
    def __init__(self):
        self.feedback: list[dict] = []

    def create_feedback(self, **kwargs):
        self.feedback.append(kwargs)


def login(client, username: str) -> dict:
    token = client.post("/auth/login", json={"username": username, "password": f"{username}123"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


@pytest.fixture
def chat_client(client):
    client.app.state.graph = build_graph(FakeLLM(), FakeSearcher([0.9]), InMemorySaver())
    return client


def ask(client, headers) -> str:
    events = parse_sse(client.post("/chat/stream", json={"message": "password policy?"}, headers=headers).text)
    return events[-1][1]["run_id"]


def test_every_answer_has_a_run_id(chat_client):
    run_id = ask(chat_client, login(chat_client, "viewer"))

    assert len(run_id) == 36


def test_feedback_is_sent_to_langsmith_for_your_own_answer(chat_client):
    langsmith = FakeLangSmith()
    chat_client.app.state.feedback_client = langsmith
    headers = login(chat_client, "viewer")
    run_id = ask(chat_client, headers)

    response = chat_client.post("/feedback", json={"run_id": run_id, "score": 0, "comment": "too long"},
                                headers=headers)

    assert response.json() == {"recorded": True, "sent_to_langsmith": True}
    assert langsmith.feedback == [{"run_id": run_id, "key": "user_rating", "score": 0, "comment": "too long"}]


def test_feedback_is_recorded_even_without_langsmith(chat_client):
    headers = login(chat_client, "viewer")
    run_id = ask(chat_client, headers)

    response = chat_client.post("/feedback", json={"run_id": run_id, "score": 1}, headers=headers)

    assert response.json() == {"recorded": True, "sent_to_langsmith": False}


def test_you_cannot_rate_someone_elses_answer(chat_client):
    run_id = ask(chat_client, login(chat_client, "admin"))

    response = chat_client.post("/feedback", json={"run_id": run_id, "score": 0}, headers=login(chat_client, "viewer"))

    assert response.status_code == 404


def test_score_must_be_zero_or_one(chat_client):
    headers = login(chat_client, "viewer")
    run_id = ask(chat_client, headers)

    response = chat_client.post("/feedback", json={"run_id": run_id, "score": 5}, headers=headers)

    assert response.status_code == 422
