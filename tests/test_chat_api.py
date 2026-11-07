import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.graph.builder import build_graph
from tests.fakes import GOOD_ANSWER, FakeLLM, FakeSearcher


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture
def chat_client(client):
    client.app.state.graph = build_graph(FakeLLM(), FakeSearcher([0.9]), InMemorySaver())
    return client


def login(client, username: str) -> dict:
    token = client.post("/auth/login", json={"username": username, "password": f"{username}123"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def chat(client, headers: dict, message: str, thread_id: str | None = None) -> list[tuple[str, dict]]:
    response = client.post("/chat/stream", json={"message": message, "thread_id": thread_id}, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_sse(response.text)


def test_chat_needs_login(chat_client):
    response = chat_client.post("/chat/stream", json={"message": "hi"})

    assert response.status_code == 401


def test_empty_message_is_rejected(chat_client):
    response = chat_client.post("/chat/stream", json={"message": ""}, headers=login(chat_client, "viewer"))

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_stream_shows_each_agent_then_the_answer(chat_client):
    events = chat(chat_client, login(chat_client, "viewer"), "password policy?")

    names = [name for name, _ in events]
    nodes = [data["node"] for name, data in events if name == "node_end"]
    assert names[0] == "start"
    assert nodes == ["supervisor", "retrieval", "response", "validator"]
    assert names[-1] == "done"
    assert events[-1][1]["answer"] == GOOD_ANSWER


def test_activity_events_carry_useful_details(chat_client):
    stream = chat(chat_client, login(chat_client, "viewer"), "q")
    events = {data["node"]: data for name, data in stream if name == "node_end"}

    assert events["supervisor"]["route"] == "qa"
    assert events["supervisor"]["rationale"] == "policy question"
    assert events["retrieval"]["chunk_ids"] == ["POL-SEC-001#4"]
    assert events["validator"]["ok"] is True
    assert events["validator"]["cited"] == ["POL-SEC-001#4"]


def test_same_thread_id_continues_the_conversation(chat_client):
    headers = login(chat_client, "viewer")
    thread_id = chat(chat_client, headers, "first question")[0][1]["thread_id"]

    chat(chat_client, headers, "follow up", thread_id=thread_id)

    config = {"configurable": {"thread_id": f"viewer:{thread_id}"}}
    state = chat_client.app.state.graph.get_state(config)
    assert len(state.values["messages"]) == 4


def test_users_cannot_read_each_others_threads(chat_client):
    chat(chat_client, login(chat_client, "admin"), "secret question", thread_id="shared")

    chat(chat_client, login(chat_client, "viewer"), "my question", thread_id="shared")

    graph = chat_client.app.state.graph
    viewer_state = graph.get_state({"configurable": {"thread_id": "viewer:shared"}})
    assert viewer_state.values["messages"][0].content == "my question"


def test_missing_graph_gives_503(client):
    response = client.post("/chat/stream", json={"message": "hi"}, headers=login(client, "viewer"))

    assert response.status_code == 503
    assert response.json()["error"] == "assistant_unavailable"


def test_crash_inside_the_graph_becomes_an_error_event(chat_client):
    class BrokenSearcher:
        async def search(self, query, role):
            raise RuntimeError("pinecone exploded")

    chat_client.app.state.graph = build_graph(FakeLLM(), BrokenSearcher(), InMemorySaver())

    events = chat(chat_client, login(chat_client, "viewer"), "q")

    assert events[-1][0] == "error"
    assert "pinecone" not in events[-1][1]["message"]
