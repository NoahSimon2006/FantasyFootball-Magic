"""Trending signals on small, hand-checkable datasets.

Value scenario: a 2-team league starting one QB each, so the top two QBs start and the
third-best QB is replacement level. Values are points above that replacement player.
"""

from datetime import UTC, date, datetime, timedelta
from types import MappingProxyType

import pytest
from sqlalchemy.orm import Session

from app.services.trending import trade_volume, value_moves
from app.valuation.formats import LeagueFormat
from tests.seed import add_league, add_players, add_snapshot, add_trade

NOW = datetime(2026, 10, 15, 12, tzinfo=UTC)
TWO_QB_TEAMS = LeagueFormat(teams=2, slots=MappingProxyType({"QB": 1}))

D = date(2026, 10, 15)  # newest snapshot
EIGHT_DAYS_AGO = date(2026, 10, 7)
THREE_DAYS_AGO = date(2026, 10, 12)


def days_ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def test_trade_volume_counts_distinct_redraft_trades_in_each_window(db_session: Session) -> None:
    add_league(db_session, "redraft", league_type=0)
    add_league(db_session, "dynasty", league_type=2)
    add_trade(db_session, "t1", "redraft", days_ago(1), players=("p1", "p2"), picks=1)
    add_trade(db_session, "t2", "redraft", days_ago(2), players=("p1",))
    add_trade(db_session, "t3", "redraft", days_ago(10), players=("p1", "p3"))  # earlier window
    add_trade(db_session, "t4", "dynasty", days_ago(1), players=("p1",))  # wrong league type
    add_trade(db_session, "t5", "redraft", days_ago(20), players=("p9",))  # outside both windows

    result = trade_volume(db_session, now=NOW, days=7)

    assert [(v.player_id, v.trades, v.previous_trades) for v in result] == [
        ("p1", 2, 1),  # t1 + t2 recently, t3 before
        ("p2", 1, 0),
        ("p3", 0, 1),  # only traded in the earlier window: falling interest
    ]


def test_trade_volume_ignores_draft_pick_assets(db_session: Session) -> None:
    add_league(db_session, "redraft")
    add_trade(db_session, "t1", "redraft", days_ago(1), picks=2)

    assert trade_volume(db_session, now=NOW, days=7) == []


def test_trade_volume_with_no_trades_is_empty(db_session: Session) -> None:
    assert trade_volume(db_session, now=NOW, days=7) == []


def seed_qbs(session: Session) -> None:
    add_players(session, dict.fromkeys(["q1", "q2", "q3", "q4"], "QB"))


def test_value_moves_need_a_snapshot_at_least_days_older(db_session: Session) -> None:
    seed_qbs(db_session)
    add_snapshot(db_session, D, {"q1": 20, "q2": 18, "q3": 10, "q4": 5}, weeks=(6, 7))
    add_snapshot(db_session, THREE_DAYS_AGO, {"q1": 20, "q2": 18, "q3": 10, "q4": 5}, weeks=(6, 7))

    assert value_moves(db_session, TWO_QB_TEAMS, days=7) is None


def test_unchanged_projections_show_no_movement_despite_a_week_of_games_passing(
    db_session: Session,
) -> None:
    seed_qbs(db_session)
    points = {"q1": 20, "q2": 18, "q3": 10, "q4": 5}
    add_snapshot(db_session, EIGHT_DAYS_AGO, points, weeks=(5, 6, 7))  # week 5 still ahead
    add_snapshot(db_session, D, points, weeks=(6, 7))  # week 5 has been played

    moves = value_moves(db_session, TWO_QB_TEAMS, days=7)

    assert moves is not None
    assert [move.change for move in moves.moves] == [0.0, 0.0, 0.0, 0.0]


def test_a_rising_player_pushes_the_replacement_level_up_for_everyone_else(
    db_session: Session,
) -> None:
    seed_qbs(db_session)
    add_snapshot(
        db_session, EIGHT_DAYS_AGO, {"q1": 20, "q2": 18, "q3": 10, "q4": 5}, weeks=(5, 6, 7)
    )
    # q3's projection jumps from 10 to 19 per week.
    add_snapshot(db_session, D, {"q1": 20, "q2": 18, "q3": 19, "q4": 5}, weeks=(6, 7))

    moves = value_moves(db_session, TWO_QB_TEAMS, days=7)

    assert moves is not None
    assert moves.compared_to == EIGHT_DAYS_AGO
    # Then (weeks 6-7): q1 40, q2 36, q3 20 -> starters q1/q2, replacement = q3's 20,
    #   so values are q1 20, q2 16, q3 0.
    # Now: q1 40, q3 38, q2 36 -> starters q1/q3, replacement = q2's 36,
    #   so values are q1 4, q3 2, q2 0.
    assert {m.player_id: m.change for m in moves.moves} == {
        "q1": -16.0,
        "q2": -16.0,
        "q3": 2.0,
        "q4": 0.0,
    }
    assert [m.player_id for m in moves.moves] == ["q1", "q2", "q3", "q4"]  # biggest change first
    q3 = next(m for m in moves.moves if m.player_id == "q3")
    assert (q3.ros_then, q3.ros_now) == (20.0, 38.0)


def test_value_moves_compare_against_the_newest_snapshot_that_is_old_enough(
    db_session: Session,
) -> None:
    seed_qbs(db_session)
    add_snapshot(db_session, EIGHT_DAYS_AGO, {"q1": 20, "q2": 18, "q3": 10, "q4": 5}, (5, 6, 7))
    # Too recent to compare against (3 days old), with wild numbers that must be ignored.
    add_snapshot(db_session, THREE_DAYS_AGO, {"q1": 20, "q2": 18, "q3": 10, "q4": 99}, (6, 7))
    add_snapshot(db_session, D, {"q1": 20, "q2": 18, "q3": 10, "q4": 5}, weeks=(6, 7))

    moves = value_moves(db_session, TWO_QB_TEAMS, days=7)

    assert moves is not None
    assert moves.compared_to == EIGHT_DAYS_AGO
    assert all(move.change == 0.0 for move in moves.moves)


def test_a_player_new_to_the_projections_counts_as_zero_before(db_session: Session) -> None:
    seed_qbs(db_session)
    add_snapshot(db_session, EIGHT_DAYS_AGO, {"q1": 20, "q2": 18, "q3": 10}, weeks=(6, 7))
    add_snapshot(db_session, D, {"q1": 20, "q2": 18, "q3": 10, "q4": 30}, weeks=(6, 7))

    moves = value_moves(db_session, TWO_QB_TEAMS, days=7)

    assert moves is not None
    q4 = next(m for m in moves.moves if m.player_id == "q4")
    assert (q4.value_then, q4.ros_then) == (0.0, 0.0)
    assert q4.value_now > 0


def test_no_projections_at_all_raises_a_clear_error(db_session: Session) -> None:
    from app.services.values import ValuesUnavailableError

    with pytest.raises(ValuesUnavailableError):
        value_moves(db_session, TWO_QB_TEAMS, days=7)
