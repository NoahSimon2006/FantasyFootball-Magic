"""A fake Sleeper for the crawler and trade-ingest tests, plus their data factories.

`FakeSleeper` is an `httpx2.MockTransport` handler: it answers each URL path from canned JSON,
records every path requested, and can make chosen paths fail. Users, leagues, members and
trades are built from the real (anonymized) fixtures, so they have exactly Sleeper's shape.
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx2
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.sleeper.client import SleeperClient
from tests.sleeper.helpers import FakeTime, json_response, load_fixture

# A real two-team trade from the week-2 fixture: rosters 2 and 9 swap two players each.
TEMPLATE_TRADE_ID = "1407974116450992128"

# What Sleeper answers when there's nothing there: a null body for a username it doesn't know,
# an empty list for a user with no leagues that season or a week without transactions. Any
# other request a test didn't describe fails that test.
_NOTHING_THERE: list[tuple[re.Pattern[str], Any]] = [
    (re.compile(r"/user/[^/]+"), None),
    (re.compile(r"/user/[^/]+/leagues/nfl/\d+"), []),
    (re.compile(r"/league/[^/]+/transactions/\d+"), []),
]


class FakeSleeper:
    """Sleeper's API as a dict from URL path (without the `/v1` prefix) to JSON payload."""

    def __init__(self) -> None:
        self.routes: dict[str, Any] = {}
        self.failing: set[str] = set()  # paths that answer HTTP 503
        self.requests: list[str] = []  # every path requested, in order

    def add_user(self, username: str, user_id: str) -> None:
        user: dict[str, Any] = load_fixture("user.json")
        self.routes[f"/user/{username}"] = {**user, "user_id": user_id, "username": username}

    def add_leagues(self, user_id: str, season: int, *leagues: dict[str, Any]) -> None:
        self.routes[f"/user/{user_id}/leagues/nfl/{season}"] = list(leagues)

    def add_members(self, league_id: str, *user_ids: str) -> None:
        [member, *_] = load_fixture("league_users.json")
        self.routes[f"/league/{league_id}/users"] = [
            {**member, "league_id": league_id, "user_id": user_id} for user_id in user_ids
        ]

    def add_week(self, league_id: str, week: int, transactions: list[dict[str, Any]]) -> None:
        self.routes[f"/league/{league_id}/transactions/{week}"] = transactions

    def fail(self, path: str) -> None:
        self.failing.add(path)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path.removeprefix("/v1")
        self.requests.append(path)
        if path in self.failing:
            return httpx2.Response(503)
        if path in self.routes:
            return json_response(self.routes[path])
        for pattern, answer in _NOTHING_THERE:
            if pattern.fullmatch(path):
                return json_response(answer)
        raise AssertionError(f"unexpected Sleeper request: {request.url}")


def make_client(fake: FakeSleeper) -> SleeperClient:
    """A real `SleeperClient` talking to `fake`, on fake time so nothing really waits.

    One attempt per request (no retries), so a failing path costs exactly one request of a
    run's budget and the tests' request counts stay easy to work out.
    """
    fake_time = FakeTime()
    return SleeperClient(
        transport=httpx2.MockTransport(fake),
        sleep=fake_time.sleep,
        clock=fake_time.clock,
        max_attempts=1,
    )


def make_league(
    league_id: str,
    *,
    season: int = 2026,
    league_type: int | None = 0,
    status: str = "in_season",
    total_rosters: int = 12,
    trade_deadline: int | None = 11,
) -> dict[str, Any]:
    """A league as Sleeper sends it: the real fixture league (12-team full-PPR redraft) with
    these fields replaced."""
    league: dict[str, Any] = load_fixture("user_leagues.json")[0]
    # Sleeper sends the season as a string.
    league.update(
        league_id=league_id, season=str(season), status=status, total_rosters=total_rosters
    )
    league["settings"].update(type=league_type, trade_deadline=trade_deadline)
    return league


def make_trade(transaction_id: str, *, week: int, status: str = "complete") -> dict[str, Any]:
    """A two-team trade as Sleeper sends it: a real fixture trade with a new id and week."""
    [template] = [
        tx
        for tx in load_fixture("transactions_trade.json")
        if tx["transaction_id"] == TEMPLATE_TRADE_ID
    ]
    return {**template, "transaction_id": transaction_id, "leg": week, "status": status}


@contextmanager
def recorded_sql(session: Session) -> Iterator[list[str]]:
    """Collect the text of every SQL statement `session` sends while the block runs."""
    statements: list[str] = []
    connection = session.connection()

    def record(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        statements.append(statement)

    event.listen(connection, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(connection, "before_cursor_execute", record)
