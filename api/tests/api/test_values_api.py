"""GET /api/v1/values against a small, known projection snapshot in the test database."""

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Player, ProjectionSnapshot
from app.deps import get_db
from app.main import app

TODAY = date(2026, 10, 15)
LAST_WEEK = date(2026, 10, 8)

# player_id: (position, weekly std points, weekly receptions) for weeks 6 and 7
POOL: dict[str, tuple[str, float, float]] = {
    "q1": ("QB", 25.0, 0.0), "q2": ("QB", 22.0, 0.0), "q3": ("QB", 20.0, 0.0),
    "q4": ("QB", 18.0, 0.0), "q5": ("QB", 15.0, 0.0),
    "r1": ("RB", 16.0, 4.0), "r2": ("RB", 14.0, 1.0), "r3": ("RB", 9.0, 2.0),
    "w1": ("WR", 12.0, 7.0), "w2": ("WR", 10.0, 6.0), "w3": ("WR", 6.0, 3.0),
    "t1": ("TE", 8.0, 5.0),
}  # fmt: skip


def make_player(player_id: str, position: str) -> Player:
    return Player(
        player_id=player_id,
        full_name=f"Player {player_id.upper()}",
        position=position,
        team="DEN",
        age=None,
        years_exp=None,
        status="Active",
        injury_status=None,
        updated_at=datetime(2026, 10, 15, tzinfo=UTC),
    )


def snapshot(
    day: date, player_id: str, week: int, std: float, catches: float
) -> ProjectionSnapshot:
    return ProjectionSnapshot(
        snapshot_date=day,
        season=2026,
        week=week,
        player_id=player_id,
        pts_ppr=std + catches,
        pts_half_ppr=std + 0.5 * catches,
        pts_std=std,
    )


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(db_session: Session) -> Session:
    db_session.add_all([make_player(pid, pos) for pid, (pos, _, _) in POOL.items()])
    db_session.add(make_player("k1", "K"))
    db_session.add(make_player("injured", "WR"))  # known player with no projection
    db_session.flush()
    for pid, (_, std, catches) in POOL.items():
        for week in (6, 7):
            db_session.add(snapshot(TODAY, pid, week, std, catches))
    # An older snapshot with very different numbers: must be ignored.
    db_session.add(snapshot(LAST_WEEK, "q5", 6, 99.0, 0.0))
    db_session.add(snapshot(TODAY, "k1", 6, 9.0, 0.0))
    db_session.flush()
    return db_session


def test_values_without_any_projections_is_a_clear_503(client: TestClient) -> None:
    response = client.get("/api/v1/values")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "VALUES_UNAVAILABLE"


def test_values_come_from_the_latest_snapshot_ranked_by_value(
    client: TestClient, seeded: Session
) -> None:
    body = client.get("/api/v1/values", params={"teams": 2}).json()

    assert (body["snapshot_date"], body["season"], body["from_week"]) == ("2026-10-15", 2026, 6)
    ranks = [player["overall_rank"] for player in body["players"]]
    assert ranks == sorted(ranks)
    values = [player["value"] for player in body["players"]]
    assert values == sorted(values, reverse=True)
    q5 = next(p for p in body["players"] if p["player_id"] == "q5")
    assert q5["ros_points"] == 30.0  # 15 + 15 from today's snapshot, not last week's 99


def test_kickers_and_unprojected_players_are_not_listed(
    client: TestClient, seeded: Session
) -> None:
    body = client.get("/api/v1/values", params={"teams": 2}).json()

    listed = {player["player_id"] for player in body["players"]}
    assert listed == set(POOL)
    assert body["total"] == len(POOL)


def test_position_filter_and_pagination(client: TestClient, seeded: Session) -> None:
    everyone = client.get("/api/v1/values", params={"teams": 2, "position": "QB"}).json()
    page = client.get(
        "/api/v1/values", params={"teams": 2, "position": "QB", "limit": 2, "offset": 1}
    ).json()

    assert everyone["total"] == 5
    assert {p["position"] for p in everyone["players"]} == {"QB"}
    assert [p["player_id"] for p in page["players"]] == [
        p["player_id"] for p in everyone["players"][1:3]
    ]
    assert page["total"] == 5


def test_superflex_raises_the_top_quarterback(client: TestClient, seeded: Session) -> None:
    def q1_value(superflex: bool) -> float:
        body = client.get(
            "/api/v1/values", params={"teams": 2, "superflex": superflex, "position": "QB"}
        ).json()
        return float(next(p["value"] for p in body["players"] if p["player_id"] == "q1"))

    assert q1_value(superflex=True) > q1_value(superflex=False)


def test_ppr_setting_changes_projected_points(client: TestClient, seeded: Session) -> None:
    def w1_points(ppr: float) -> float:
        body = client.get("/api/v1/values", params={"teams": 2, "ppr": ppr}).json()
        return float(next(p["ros_points"] for p in body["players"] if p["player_id"] == "w1"))

    assert w1_points(1.0) == 38.0  # (12 + 7 catches) x 2 weeks
    assert w1_points(0.0) == 24.0  # 12 x 2 weeks


@pytest.mark.parametrize(
    "params", [{"teams": 1}, {"limit": 500}, {"ppr": 2}, {"position": "K"}, {"offset": -1}]
)
def test_bad_query_parameters_get_the_standard_422_shape(
    client: TestClient, params: dict[str, str | int | float]
) -> None:
    response = client.get("/api/v1/values", params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_route_uses_the_standard_error_shape(client: TestClient) -> None:
    response = client.get("/api/v1/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
