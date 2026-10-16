from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.valuation.trade import DEPTH_DECAY, EVEN_THRESHOLD
from tests.seed import add_league, add_players, add_snapshot, add_trade


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_parameters_are_the_codes_real_constants(client: TestClient) -> None:
    params = client.get("/api/v1/methodology").json()["parameters"]

    assert (params["depth_decay"], params["even_threshold"]) == (DEPTH_DECAY, EVEN_THRESHOLD)
    assert params["valued_positions"] == ["QB", "RB", "WR", "TE"]
    assert params["lineup_1qb"]["slots"] == {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1}
    assert params["lineup_superflex"]["slots"]["SUPER_FLEX"] == 1


def test_empty_database_reports_no_data_honestly(client: TestClient) -> None:
    data = client.get("/api/v1/methodology").json()["data"]

    assert data == {
        "latest_projection_snapshot": None,
        "projection_snapshots": 0,
        "players": 0,
        "leagues": 0,
        "trades": 0,
    }


def test_data_counts_reflect_what_is_stored(client: TestClient, db_session: Session) -> None:
    add_players(db_session, {"q1": "QB", "q2": "QB"})
    add_snapshot(db_session, date(2026, 10, 8), {"q1": 20}, weeks=(6, 7))
    add_snapshot(db_session, date(2026, 10, 15), {"q1": 20, "q2": 15}, weeks=(6,))
    add_league(db_session, "L1")
    add_trade(db_session, "t1", "L1", datetime(2026, 10, 14, tzinfo=UTC), players=("q1",))

    data = client.get("/api/v1/methodology").json()["data"]

    assert data == {
        "latest_projection_snapshot": "2026-10-15",
        "projection_snapshots": 2,
        "players": 2,
        "leagues": 1,
        "trades": 1,
    }
