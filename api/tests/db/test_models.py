"""The schema holds what ingest writes: relationships, cascades, keys, and isolation.

Every test here runs against the migrated test database through the `db_session`
fixture, and everything it writes is rolled back afterwards.
"""

from datetime import UTC, date, datetime

import pytest
from psycopg import errors as pg_errors
from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import CrawlUser, League, ProjectionSnapshot, Trade, TradeAsset

LEAGUE_ID = "test-league-1"
TRANSACTION_ID = "test-trade-1"
ISOLATION_PROBE_USER_ID = "test-isolation-probe"


def make_league() -> League:
    """A 12-team, 1QB, full-PPR redraft league."""
    return League(
        league_id=LEAGUE_ID,
        season=2026,
        status="in_season",
        league_type=0,
        total_rosters=12,
        ppr=1.0,
        is_superflex=False,
        trade_deadline=11,
    )


def make_trade(league: League) -> Trade:
    """Roster 1 sends a player to roster 4 for $15 of FAAB."""
    return Trade(
        transaction_id=TRANSACTION_ID,
        league=league,
        season=2026,
        week=6,
        created_at=datetime(2026, 10, 12, 17, 30, tzinfo=UTC),
        roster_ids=[1, 4],
        raw={"type": "trade", "status": "complete", "adds": {"4046": 4}, "drops": {"4046": 1}},
        assets=[
            TradeAsset(asset_type="player", player_id="4046", from_roster_id=1, to_roster_id=4),
            TradeAsset(asset_type="faab", faab_amount=15, from_roster_id=4, to_roster_id=1),
        ],
    )


def make_projection_snapshot(snapshot_date: date) -> ProjectionSnapshot:
    """One player's week-7 projection as fetched on `snapshot_date`."""
    return ProjectionSnapshot(
        snapshot_date=snapshot_date,
        season=2026,
        week=7,
        player_id="6794",
        pts_ppr=19.2,
        pts_half_ppr=16.0,
        pts_std=12.8,
    )


def count_rows(session: Session, model: type[Base], *where: ColumnElement[bool]) -> int:
    """How many rows of `model` match, counted by Postgres (not the session's memory)."""
    return session.execute(select(func.count()).select_from(model).where(*where)).scalar_one()


def test_league_trade_and_assets_read_back_through_relationships(db_session: Session) -> None:
    db_session.add(make_trade(make_league()))
    db_session.flush()
    # Forget every Python object, so everything below is loaded back from Postgres.
    db_session.expunge_all()

    league = db_session.get_one(League, LEAGUE_ID)
    [trade] = league.trades
    assets = sorted(
        (a.asset_type, a.player_id, a.faab_amount, a.from_roster_id, a.to_roster_id)
        for a in trade.assets
    )

    assert trade.roster_ids == [1, 4]
    assert trade.raw["adds"] == {"4046": 4}
    assert assets == [("faab", None, 15, 4, 1), ("player", "4046", None, 1, 4)]
    assert trade.assets[0].trade.league is league


def test_deleting_a_trade_deletes_its_assets(db_session: Session) -> None:
    db_session.add(make_trade(make_league()))
    db_session.flush()

    # A bulk DELETE statement skips the ORM's own cascade, so only the foreign key's
    # ON DELETE CASCADE in the database can remove the asset rows.
    db_session.execute(delete(Trade).where(Trade.transaction_id == TRANSACTION_ID))

    assert count_rows(db_session, TradeAsset, TradeAsset.transaction_id == TRANSACTION_ID) == 0


def test_deleting_a_league_deletes_its_trades_and_their_assets(db_session: Session) -> None:
    db_session.add(make_trade(make_league()))
    db_session.flush()
    db_session.expunge_all()

    db_session.delete(db_session.get_one(League, LEAGUE_ID))
    db_session.flush()

    assert count_rows(db_session, Trade, Trade.league_id == LEAGUE_ID) == 0
    assert count_rows(db_session, TradeAsset, TradeAsset.transaction_id == TRANSACTION_ID) == 0


def test_projection_snapshot_rejects_a_second_row_for_the_same_day(db_session: Session) -> None:
    db_session.add(make_projection_snapshot(date(2026, 10, 14)))
    db_session.flush()
    # Drop the first object from the session, so the duplicate reaches Postgres instead of
    # being caught by the ORM's own identity check.
    db_session.expunge_all()

    db_session.add(make_projection_snapshot(date(2026, 10, 14)))
    with pytest.raises(IntegrityError) as excinfo:
        db_session.flush()

    assert isinstance(excinfo.value.orig, pg_errors.UniqueViolation)


def test_projection_snapshot_accepts_the_same_player_week_on_a_new_day(
    db_session: Session,
) -> None:
    db_session.add(make_projection_snapshot(date(2026, 10, 14)))
    db_session.add(make_projection_snapshot(date(2026, 10, 15)))
    db_session.flush()

    assert count_rows(db_session, ProjectionSnapshot, ProjectionSnapshot.player_id == "6794") == 2


def test_database_stamps_discovered_at_as_a_timezone_aware_time(db_session: Session) -> None:
    user = CrawlUser(user_id="test-user-1")
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)

    # timestamptz comes back with a UTC offset; a plain `timestamp` column would be naive.
    assert user.discovered_at.utcoffset() is not None


# The next two tests are a pair and rely on pytest running a file's tests in order.
def test_isolation_part_1_a_committed_row_is_visible_within_its_test(db_session: Session) -> None:
    db_session.add(CrawlUser(user_id=ISOLATION_PROBE_USER_ID))
    db_session.commit()  # a real commit, exactly as app code would do

    assert count_rows(db_session, CrawlUser, CrawlUser.user_id == ISOLATION_PROBE_USER_ID) == 1


def test_isolation_part_2_rows_from_the_previous_test_are_gone(db_session: Session) -> None:
    assert count_rows(db_session, CrawlUser, CrawlUser.user_id == ISOLATION_PROBE_USER_ID) == 0
