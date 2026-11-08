from ui.api_client import parse_sse
from ui.panel import describe


def test_parse_sse_reads_event_and_json_data():
    lines = [
        "event: start",
        'data: {"thread_id": "abc"}',
        "",
        "event: token",
        'data: {"text": "Hi"}',
        "",
    ]

    assert list(parse_sse(lines)) == [("start", {"thread_id": "abc"}), ("token", {"text": "Hi"})]


def test_parse_sse_ignores_data_without_an_event_line():
    assert list(parse_sse(['data: {"x": 1}', ""])) == []


def test_tokens_are_not_shown_in_the_panel():
    assert describe("token", {"text": "Hi"}) is None


def test_supervisor_step_shows_route_rationale_and_search():
    title, detail = describe("node_end", {"node": "supervisor", "route": "qa",
                                          "rationale": "policy question", "search_query": "password policy"})

    assert title == "Supervisor"
    assert "**qa**" in detail and "policy question" in detail and "password policy" in detail


def test_retrieval_step_lists_chunks_or_says_nothing_found():
    _, found = describe("node_end", {"node": "retrieval", "found": 1, "chunk_ids": ["POL-SEC-001#4"]})
    _, empty = describe("node_end", {"node": "retrieval", "found": 0, "chunk_ids": []})

    assert "`POL-SEC-001#4`" in found
    assert "nothing above the minimum score" in empty


def test_validator_step_shows_pass_or_reject_reason():
    _, passed = describe("node_end", {"node": "validator", "ok": True, "cited": ["POL-SEC-001#4"],
                                      "unknown": [], "reason": ""})
    _, rejected = describe("node_end", {"node": "validator", "ok": False, "cited": [],
                                        "unknown": [], "reason": "The answer has no citations."})

    assert "passed" in passed and "`POL-SEC-001#4`" in passed
    assert "rejected" in rejected and "no citations" in rejected


def test_memory_event_is_shown_in_the_panel():
    title, detail = describe("memory", {"thread_messages": 4})

    assert title == "Memory"
    assert "**4** messages" in detail
