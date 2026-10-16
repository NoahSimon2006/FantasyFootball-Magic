"""ingest_players: Sleeper's player dump, filtered to fantasy positions and upserted.

Each test runs against the test database through `db_session` (rolled back afterwards) and
a SleeperClient on a mock transport, so nothing reaches the real Sleeper API.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Player
from app.ingest.players import ROWS_PER_STATEMENT, ingest_players
from tests.ingest.fake_sleeper_basic import (
    PLAYERS_PATH,
    FakeSleeper,
    make_client,
    players_dump,
    sleeper_player,
)
from tests.sleeper.helpers import load_fixture

FIRST_RUN = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
SECOND_RUN = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def ingest(session: Session, dump: dict[str, Any], *, now: datetime = FIRST_RUN) -> int:
    """Run ingest_players against a fake Sleeper whose player dump is `dump`."""
    with make_client(FakeSleeper({PLAYERS_PATH: dump})) as client:
        return ingest_players(session, client, now=now)


def player_count(session: Session) -> int:
    return session.execute(select(func.count()).select_from(Player)).scalar_one()


def test_keeps_only_qb_rb_wr_te_k_and_def(db_session: Session) -> None:
    positions = ["QB", "RB", "WR", "TE", "K", "DEF", "LB", "OT", "CB"]
    dump = players_dump(
        *(sleeper_player(f"id-{position}", position=position) for position in positions),
        sleeper_player("id-none", position=None),
    )

    ingest(db_session, dump)

    assert set(db_session.scalars(select(Player.player_id))) == {
        "id-QB",
        "id-RB",
        "id-WR",
        "id-TE",
        "id-K",
        "id-DEF",
    }


def test_returns_the_number_of_rows_written(db_session: Session) -> None:
    dump = players_dump(
        sleeper_player("1", position="QB"),
        sleeper_player("2", position="TE"),
        sleeper_player("3", position="LB"),
    )

    assert ingest(db_session, dump) == 2


def test_stores_every_column_from_sleeper(db_session: Session) -> None:
    dump = players_dump(
        sleeper_player(
            "4046",
            position="QB",
            team="KC",
            full_name="Test Quarterback",
            age=31,
            years_exp=9,
            status="Active",
            injury_status="Questionable",
        )
    )

    ingest(db_session, dump)

    row = db_session.execute(
        select(
            Player.player_id,
            Player.full_name,
            Player.position,
            Player.team,
            Player.age,
            Player.years_exp,
            Player.status,
            Player.injury_status,
            Player.updated_at,
        )
    ).one()
    assert tuple(row) == (
        "4046",
        "Test Quarterback",
        "QB",
        "KC",
        31,
        9,
        "Active",
        "Questionable",
        FIRST_RUN,
    )


def test_team_defense_from_a_real_response_is_stored_under_its_team_name(
    db_session: Session,
) -> None:
    # Sleeper sends no full_name for a defense; the name comes from first + last name.
    ingest(db_session, load_fixture("players_subset.json"))

    name = db_session.scalar(select(Player.full_name).where(Player.player_id == "DEN"))
    assert name == "Denver Broncos"


def test_running_twice_keeps_one_row_per_player(db_session: Session) -> None:
    dump = players_dump(sleeper_player("1"), sleeper_player("2"), sleeper_player("3"))
    ingest(db_session, dump)

    ingest(db_session, dump, now=SECOND_RUN)

    assert player_count(db_session) == 3


def test_rerun_updates_a_player_who_changed_teams(db_session: Session) -> None:
    ingest(db_session, players_dump(sleeper_player("1", team="KC")))

    ingest(db_session, players_dump(sleeper_player("1", team="BUF")), now=SECOND_RUN)

    # A column query reads Postgres directly; an ORM object could be a stale cached copy.
    assert db_session.scalar(select(Player.team).where(Player.player_id == "1")) == "BUF"


def test_rerun_stamps_updated_at_with_the_new_run_time(db_session: Session) -> None:
    dump = players_dump(sleeper_player("1"))
    ingest(db_session, dump)

    ingest(db_session, dump, now=SECOND_RUN)

    assert db_session.scalar(select(Player.updated_at)) == SECOND_RUN


def test_more_players_than_one_statement_holds_are_all_written(db_session: Session) -> None:
    how_many = 2 * ROWS_PER_STATEMENT + 1  # two full statements and a partial one
    dump = players_dump(*(sleeper_player(str(number)) for number in range(how_many)))

    ingest(db_session, dump)

    assert player_count(db_session) == how_many
