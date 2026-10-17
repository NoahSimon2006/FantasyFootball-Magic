"""GET /api/v1/trending end to end through FastAPI, against the test database."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from tests.seed import add_league, add_players, add_snapshot, add_trade


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_trending_with_no_data_is_an_empty_200(client: TestClient) -> None:
    response = client.get("/api/v1/trending")

    assert response.status_code == 200
    body = response.json()
    assert body["most_traded"] == []
    assert (body["risers"], body["fallers"]) == ([], [])
    assert body["compared_to"] is None


def test_trade_volume_works_before_any_projections_exist(
    client: TestClient, db_session: Session
) -> None:
    add_players(db_session, {"q1": "QB"})
    add_league(db_session, "L1")
    add_trade(db_session, "t1", "L1", datetime.now(UTC) - timedelta(days=1), players=("q1",))

    body = client.get("/api/v1/trending").json()

    assert [(t["player"]["name"], t["trades"], t["change"]) for t in body["most_traded"]] == [
        ("Player q1", 1, 1)
    ]
    assert body["risers"] == []


def test_trending_reports_most_traded_players_and_value_risers_and_fallers(
    client: TestClient, db_session: Session
) -> None:
    add_players(db_session, dict.fromkeys(["q1", "q2", "q3", "q4"], "QB"))
    add_league(db_session, "L1")
    add_trade(db_session, "t1", "L1", datetime.now(UTC) - timedelta(days=1), players=("q3",))
    add_snapshot(db_session, date(2026, 10, 7), {"q1": 20, "q2": 18, "q3": 10, "q4": 5}, (5, 6, 7))
    add_snapshot(db_session, date(2026, 10, 15), {"q1": 20, "q2": 18, "q3": 19, "q4": 5}, (6, 7))

    body = client.get("/api/v1/trending", params={"teams": 2, "days": 7}).json()

    assert body["most_traded"][0]["player"]["player_id"] == "q3"
    assert (body["snapshot_date"], body["compared_to"]) == ("2026-10-15", "2026-10-07")
    assert [(m["player"]["player_id"], m["change"]) for m in body["risers"]] == [("q3", 2.0)]
    assert [(m["player"]["player_id"], m["change"]) for m in body["fallers"]] == [
        ("q1", -16.0),
        ("q2", -16.0),
    ]
    assert body["risers"][0]["value_now"] == 2.0
    assert body["risers"][0]["ros_points_then"] == 20.0


def test_short_history_still_reports_the_latest_snapshot(
    client: TestClient, db_session: Session
) -> None:
    add_players(db_session, {"q1": "QB", "q2": "QB"})
    add_snapshot(db_session, date(2026, 10, 15), {"q1": 20, "q2": 18}, (6, 7))

    body = client.get("/api/v1/trending").json()

    # A snapshot exists but nothing is 7+ days older: "history building", not "no data".
    assert (body["snapshot_date"], body["compared_to"]) == ("2026-10-15", None)
    assert (body["risers"], body["fallers"]) == ([], [])


def test_limit_caps_every_list(client: TestClient, db_session: Session) -> None:
    add_players(db_session, dict.fromkeys(["q1", "q2", "q3", "q4"], "QB"))
    add_snapshot(db_session, date(2026, 10, 7), {"q1": 20, "q2": 18, "q3": 10, "q4": 5}, (5, 6, 7))
    add_snapshot(db_session, date(2026, 10, 15), {"q1": 20, "q2": 18, "q3": 19, "q4": 5}, (6, 7))

    body = client.get("/api/v1/trending", params={"teams": 2, "limit": 1}).json()

    assert len(body["fallers"]) == 1


@pytest.mark.parametrize("params", [{"days": 0}, {"days": 31}, {"limit": 0}, {"limit": 51}])
def test_bad_parameters_get_the_standard_422(client: TestClient, params: dict[str, int]) -> None:
    response = client.get("/api/v1/trending", params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
