"""POST /api/v1/trades/evaluate against a small, known projection snapshot."""

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Player, ProjectionSnapshot
from app.deps import get_db
from app.main import app

TODAY = date(2026, 10, 15)

# player_id: (position, weekly points) for weeks 6 and 7, full PPR = std here (no catches).
POOL = {"q1": ("QB", 25.0), "q2": ("QB", 20.0), "q3": ("QB", 10.0), "r1": ("RB", 18.0)}


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(db_session: Session) -> Session:
    now = datetime(2026, 10, 15, tzinfo=UTC)
    for pid, position in [*((p, pos) for p, (pos, _) in POOL.items()), ("injured", "WR")]:
        db_session.add(
            Player(
                player_id=pid,
                full_name=f"Player {pid}",
                position=position,
                team=None,
                age=None,
                years_exp=None,
                status=None,
                injury_status=None,
                updated_at=now,
            )
        )
    db_session.flush()
    for pid, (_, points) in POOL.items():
        for week in (6, 7):
            db_session.add(
                ProjectionSnapshot(
                    snapshot_date=TODAY,
                    season=2026,
                    week=week,
                    player_id=pid,
                    pts_ppr=points,
                    pts_half_ppr=points,
                    pts_std=points,
                )
            )
    db_session.flush()
    return db_session


def evaluate(client: TestClient, **body: object) -> dict[str, object]:
    response = client.post("/api/v1/trades/evaluate", json={"teams": 2, **body})
    assert response.status_code == 200, response.text
    result: dict[str, object] = response.json()
    return result


def test_trade_verdict_goes_to_the_side_receiving_more_value(
    client: TestClient, seeded: Session
) -> None:
    # 2 teams x 1 QB slot: q1 and q2 start, q3 (20 ROS points) is replacement level.
    # q1 = 50 - 20 = 30 value, q2 = 40 - 20 = 20 value.
    result = evaluate(client, receives_a=["q1"], receives_b=["q2"])

    assert result["verdict"] == "a"
    assert result["margin"] == 10.0
    side_a = result["side_a"]
    assert isinstance(side_a, dict)
    assert side_a["players"][0]["name"] == "Player q1"


def test_every_verdict_comes_with_its_drivers_and_method(
    client: TestClient, seeded: Session
) -> None:
    result = evaluate(client, receives_a=["q1"], receives_b=["q2", "q3"])

    assert result["method"] == "projection_vor_v0"
    drivers = result["drivers"]
    assert isinstance(drivers, list)
    assert [d["kind"] for d in drivers][0] == "value_gap"
    assert all(set(d) == {"kind", "side", "amount", "label"} for d in drivers)


def test_known_player_without_projection_counts_as_zero(
    client: TestClient, seeded: Session
) -> None:
    result = evaluate(client, receives_a=["q2"], receives_b=["injured"])

    side_b = result["side_b"]
    assert isinstance(side_b, dict)
    assert side_b["adjusted_total"] == 0.0
    assert side_b["players"][0]["overall_rank"] is None
    assert result["verdict"] == "a"


def test_unknown_player_id_is_a_404_not_a_zero(client: TestClient, seeded: Session) -> None:
    response = client.post(
        "/api/v1/trades/evaluate", json={"receives_a": ["q1"], "receives_b": ["typo"]}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PLAYER_NOT_FOUND"
    assert "typo" in response.json()["error"]["message"]


def test_a_player_on_both_sides_is_rejected(client: TestClient, seeded: Session) -> None:
    response = client.post(
        "/api/v1/trades/evaluate", json={"receives_a": ["q1"], "receives_b": ["q1"]}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_trade_without_projections_is_a_503(client: TestClient) -> None:
    response = client.post(
        "/api/v1/trades/evaluate", json={"receives_a": ["q1"], "receives_b": ["q2"]}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "VALUES_UNAVAILABLE"
