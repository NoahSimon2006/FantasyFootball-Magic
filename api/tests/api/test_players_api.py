from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Player
from app.deps import get_db
from app.main import app
from tests.seed import add_players


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(db_session: Session) -> Session:
    add_players(
        db_session,
        {
            "jefferson": "WR",  # "Player jefferson": matches by substring only
            "q_jeff": "QB",
            "rb_jeff": "RB",
            "kicker": "K",
            "te_one": "TE",
        },
    )
    # Names with a controlled shape, a free agent, and a retired player (no team).
    db_session.add_all(
        [
            Player(
                player_id="a1",
                full_name="Jeff Starts",
                position="WR",
                team="MIN",
                updated_at=datetime(2026, 10, 15, tzinfo=UTC),
            ),
            Player(
                player_id="a2",
                full_name="Zeke Jeffries",
                position="RB",
                team="DAL",
                updated_at=datetime(2026, 10, 15, tzinfo=UTC),
            ),
            Player(
                player_id="a3",
                full_name="Retired Jeff",
                position="WR",
                team=None,
                updated_at=datetime(2026, 10, 15, tzinfo=UTC),
            ),
            Player(
                player_id="a4",
                full_name="Pat 50%_Off",
                position="TE",
                team="NE",
                updated_at=datetime(2026, 10, 15, tzinfo=UTC),
            ),
        ]
    )
    db_session.flush()
    return db_session


def names(client: TestClient, **params: str | int) -> list[str]:
    response = client.get("/api/v1/players", params=params)
    assert response.status_code == 200, response.text
    return [player["name"] for player in response.json()["players"]]


def test_search_is_case_insensitive_and_ranks_prefix_matches_first(
    client: TestClient, seeded: Session
) -> None:
    result = names(client, q="JEFF")

    assert result[0] == "Jeff Starts"  # starts with the query
    assert "Zeke Jeffries" in result  # merely contains it
    assert result.index("Jeff Starts") < result.index("Zeke Jeffries")


def test_players_without_a_team_and_kickers_are_not_searchable(
    client: TestClient, seeded: Session
) -> None:
    result = names(client, q="jeff")

    assert "Retired Jeff" not in result  # no NFL team
    assert not any("kicker" in name for name in result)


def test_position_filter_and_limit(client: TestClient, seeded: Session) -> None:
    assert names(client, q="jeff", position="RB") == ["Player rb_jeff", "Zeke Jeffries"]
    assert len(names(client, q="jeff", limit=1)) == 1


def test_like_wildcards_in_the_query_are_taken_literally(
    client: TestClient, seeded: Session
) -> None:
    assert names(client, q="50%_") == ["Pat 50%_Off"]
    assert names(client, q="%%") == []  # would match everything if not escaped


def test_response_has_the_display_fields(client: TestClient, seeded: Session) -> None:
    player = client.get("/api/v1/players", params={"q": "Jeff Starts"}).json()["players"][0]

    assert player == {"player_id": "a1", "name": "Jeff Starts", "position": "WR", "team": "MIN"}


@pytest.mark.parametrize("params", [{}, {"q": "j"}, {"q": "x" * 51}, {"q": "ab", "limit": 0}])
def test_bad_parameters_get_the_standard_422(
    client: TestClient, params: dict[str, str | int]
) -> None:
    response = client.get("/api/v1/players", params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
