import json
import os
from collections.abc import Iterable, Iterator

import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


class ApiError(Exception):
    def __init__(self, status: int, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.retry_after = retry_after


def parse_sse(lines: Iterable[str]) -> Iterator[tuple[str, dict]]:
    event = None
    for line in lines:
        if line.startswith("event: "):
            event = line.removeprefix("event: ")
        elif line.startswith("data: ") and event:
            yield event, json.loads(line.removeprefix("data: "))
            event = None


def _raise_for_error(response: httpx.Response) -> None:
    if response.is_success:
        return
    response.read()
    try:
        body = response.json()
    except ValueError:
        body = {}
    raise ApiError(response.status_code, body.get("message", "Unexpected error from the API."),
                   body.get("retry_after"))


class ApiClient:
    def __init__(self, base_url: str = API_BASE_URL, timeout_s: float = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def login(self, username: str, password: str) -> dict:
        try:
            response = httpx.post(f"{self.base_url}/auth/login",
                                  json={"username": username, "password": password}, timeout=10)
        except httpx.ConnectError:
            raise ApiError(0, f"Cannot reach the API at {self.base_url}. Is it running?") from None
        _raise_for_error(response)
        return response.json()

    def stream_chat(self, token: str, message: str, thread_id: str | None = None) -> Iterator[tuple[str, dict]]:
        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/chat/stream",
                json={"message": message, "thread_id": thread_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout_s,
            ) as response:
                _raise_for_error(response)
                yield from parse_sse(response.iter_lines())
        except httpx.ConnectError:
            raise ApiError(0, f"Cannot reach the API at {self.base_url}. Is it running?") from None
