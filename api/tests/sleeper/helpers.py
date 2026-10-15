"""Test helpers for the Sleeper client: saved real responses, fake time, a scripted transport."""

import json
from pathlib import Path
from typing import Any

import httpx2

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "sleeper"


def load_fixture(name: str) -> Any:
    """A real Sleeper response saved (and anonymized) in tests/fixtures/sleeper/."""
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def json_response(
    payload: Any, status: int = 200, headers: dict[str, str] | None = None
) -> httpx2.Response:
    """A JSON response. Unlike `httpx2.Response(json=None)`, a `None` payload produces the
    literal `null` body that Sleeper really sends."""
    return httpx2.Response(
        status,
        content=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )


class FakeTime:
    """A clock that only moves when something sleeps on it. Records every sleep, so tests can
    assert on backoff and rate-limit waits without actually waiting."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class ScriptedSleeper:
    """`httpx2.MockTransport` handler that plays back outcomes in order and records requests.

    An outcome is either a response or an exception to raise (a timeout, a dropped
    connection). A request beyond the script fails the test, so "no further HTTP calls" is
    enforced, not assumed.
    """

    def __init__(self, *outcomes: httpx2.Response | Exception) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if not self._outcomes:
            raise AssertionError(f"unexpected extra request: {request.method} {request.url}")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
