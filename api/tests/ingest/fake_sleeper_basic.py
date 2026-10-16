"""A small fake Sleeper for the ingest tests: canned responses per URL path, served through
`httpx2.MockTransport`, so no test can reach the real API.

The payload factories build data in Sleeper's own JSON shape (seasons as strings, and so
on), so every test also runs the real parsing in `app.sleeper.models`.
"""

from collections.abc import Mapping
from typing import Any

import httpx2

from app.sleeper.client import SleeperClient
from app.sleeper.models import SleeperPlayer
from tests.sleeper.helpers import FakeTime, json_response, load_fixture

PLAYERS_PATH = "/v1/players/nfl"
NFL_STATE_PATH = "/v1/state/nfl"


def projections_path(season: int, week: int) -> str:
    """The path of the unofficial projections endpoint (on api.sleeper.com) for one week."""
    return f"/projections/nfl/{season}/{week}"


class FakeSleeper:
    """MockTransport handler that answers each URL path in `routes`.

    A route's value is a JSON payload, or an `httpx2.Response` to send as is (e.g. an error
    status). `routes` stays editable, so a test can change what Sleeper says between two
    runs. A path missing from `routes` fails the test; `requested` records every path asked
    for, in order.
    """

    def __init__(self, routes: Mapping[str, Any] | None = None) -> None:
        self.routes: dict[str, Any] = dict(routes or {})
        self.requested: list[str] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        self.requested.append(path)
        if path not in self.routes:
            raise AssertionError(f"unexpected Sleeper request: {request.url}")
        answer = self.routes[path]
        return answer if isinstance(answer, httpx2.Response) else json_response(answer)


def make_client(fake: FakeSleeper) -> SleeperClient:
    """A real SleeperClient wired to `fake`, on fake time so rate limiting never waits."""
    fake_time = FakeTime()
    return SleeperClient(
        transport=httpx2.MockTransport(fake), sleep=fake_time.sleep, clock=fake_time.clock
    )


def sleeper_player(
    player_id: str, *, position: str | None = "WR", team: str | None = "KC", **changes: Any
) -> dict[str, Any]:
    """One value of Sleeper's `/players/nfl` map. Keyword arguments replace fields."""
    # Pydantic ignores unknown keys, so a misspelled field would silently change nothing and
    # a test could pass without testing anything.
    unknown = changes.keys() - SleeperPlayer.model_fields.keys()
    if unknown:
        raise TypeError(f"sleeper_player() got unknown SleeperPlayer fields: {sorted(unknown)}")
    return {
        "player_id": player_id,
        "first_name": "Test",
        "last_name": f"Player {player_id}",
        "full_name": f"Test Player {player_id}",
        "position": position,
        "team": team,
        "age": 26,
        "years_exp": 4,
        "status": "Active",
        "injury_status": None,
        "active": True,
        "fantasy_positions": [position] if position else None,
        **changes,
    }


def players_dump(*players: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Sleeper's `/players/nfl` body: every player, keyed by player_id."""
    return {player["player_id"]: player for player in players}


def sleeper_projection(
    player_id: str,
    *,
    season: int = 2026,
    week: int = 6,
    ppr: float = 12.0,
    half_ppr: float = 10.5,
    std: float = 9.0,
) -> dict[str, Any]:
    """One row of the projections endpoint, with its three fantasy-point totals."""
    return {
        "player_id": player_id,
        "season": str(season),
        "week": week,
        "season_type": "regular",
        "category": "proj",
        "stats": {"pts_ppr": ppr, "pts_half_ppr": half_ppr, "pts_std": std},
    }


def nfl_state(*, season: int = 2026, week: int = 6) -> dict[str, Any]:
    """Sleeper's `/state/nfl` body for a regular-season week."""
    return {
        **load_fixture("nfl_state.json"),
        "season": str(season),
        "previous_season": str(season - 1),
        "week": week,
        "display_week": week,
        "leg": week,
    }
