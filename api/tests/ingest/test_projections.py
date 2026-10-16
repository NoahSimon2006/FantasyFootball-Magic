"""ingest_projections: weekly projections saved as dated snapshots.

Each test runs against the test database through `db_session` (rolled back afterwards) and
a SleeperClient on a mock transport, so nothing reaches the real Sleeper API.
"""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ProjectionSnapshot
from app.ingest.projections import ROWS_PER_STATEMENT, ingest_projections
from tests.ingest.fake_sleeper_basic import (
    FakeSleeper,
    make_client,
    projections_path,
    sleeper_projection,
)
from tests.sleeper.helpers import load_fixture

SEASON = 2026
DAY_ONE = date(2026, 10, 14)
DAY_TWO = date(2026, 10, 15)


def ingest(
    session: Session,
    fake: FakeSleeper,
    *,
    weeks: Sequence[int] = (6,),
    snapshot_date: date = DAY_ONE,
) -> int:
    """Run ingest_projections for `weeks` of 2026 against `fake`."""
    with make_client(fake) as client:
        return ingest_projections(
            session, client, season=SEASON, weeks=weeks, snapshot_date=snapshot_date
        )


def week_six(*rows: dict[str, object]) -> FakeSleeper:
    """A fake Sleeper whose week-6 projections are `rows`."""
    return FakeSleeper({projections_path(SEASON, 6): list(rows)})


def stored_ppr(session: Session, snapshot_date: date, week: int = 6) -> dict[str, float]:
    """player_id -> stored PPR points, for one day's snapshot of one week."""
    rows = session.execute(
        select(ProjectionSnapshot.player_id, ProjectionSnapshot.pts_ppr).where(
            ProjectionSnapshot.snapshot_date == snapshot_date,
            ProjectionSnapshot.season == SEASON,
            ProjectionSnapshot.week == week,
        )
    )
    return dict(rows.all())


def test_stores_each_week_under_its_own_week_number(db_session: Session) -> None:
    fake = FakeSleeper(
        {
            projections_path(SEASON, 6): [sleeper_projection("1"), sleeper_projection("2")],
            projections_path(SEASON, 7): [
                sleeper_projection("1", week=7),
                sleeper_projection("2", week=7),
                sleeper_projection("3", week=7),
            ],
        }
    )

    ingest(db_session, fake, weeks=[6, 7])

    rows_per_week = db_session.execute(
        select(ProjectionSnapshot.week, func.count()).group_by(ProjectionSnapshot.week)
    )
    assert dict(rows_per_week.all()) == {6: 2, 7: 3}


def test_stores_all_three_scoring_formats(db_session: Session) -> None:
    ingest(db_session, week_six(sleeper_projection("1", ppr=18.5, half_ppr=15.0, std=11.5)))

    points = db_session.execute(
        select(
            ProjectionSnapshot.pts_ppr, ProjectionSnapshot.pts_half_ppr, ProjectionSnapshot.pts_std
        )
    ).one()
    assert tuple(points) == (18.5, 15.0, 11.5)


def test_every_row_of_a_real_response_is_stored(db_session: Session) -> None:
    raw = load_fixture("projections_week.json")

    ingest(db_session, week_six(*raw))

    assert len(stored_ppr(db_session, DAY_ONE)) == len(raw)


def test_rows_with_all_zero_points_are_skipped(db_session: Session) -> None:
    fake = week_six(
        sleeper_projection("projected", ppr=12.0, half_ppr=10.5, std=9.0),
        sleeper_projection("on-bye", ppr=0.0, half_ppr=0.0, std=0.0),
        # No point fields at all reads as 0 too.
        {"player_id": "no-points", "season": "2026", "week": 6, "stats": {}},
    )

    ingest(db_session, fake)

    assert set(stored_ppr(db_session, DAY_ONE)) == {"projected"}


def test_negative_projection_is_kept(db_session: Session) -> None:
    # Only all-zero rows are noise. A negative projection is a real (if bleak) forecast.
    ingest(db_session, week_six(sleeper_projection("1", ppr=-0.5, half_ppr=-0.5, std=-0.5)))

    assert stored_ppr(db_session, DAY_ONE) == {"1": -0.5}


def test_returns_the_rows_written_across_weeks_without_skipped_ones(db_session: Session) -> None:
    fake = FakeSleeper(
        {
            projections_path(SEASON, 6): [
                sleeper_projection("1"),
                sleeper_projection("2", ppr=0.0, half_ppr=0.0, std=0.0),
            ],
            projections_path(SEASON, 7): [sleeper_projection("1", week=7)],
        }
    )

    assert ingest(db_session, fake, weeks=[6, 7]) == 2


def test_same_day_rerun_overwrites_that_days_points(db_session: Session) -> None:
    ingest(db_session, week_six(sleeper_projection("1", ppr=12.0)))

    ingest(db_session, week_six(sleeper_projection("1", ppr=15.5)))

    assert stored_ppr(db_session, DAY_ONE) == {"1": 15.5}


def test_same_day_rerun_drops_a_player_no_longer_projected(db_session: Session) -> None:
    ingest(db_session, week_six(sleeper_projection("1"), sleeper_projection("2")))

    # Player 2 was ruled out later that day: Sleeper now projects him for nothing.
    ingest(
        db_session,
        week_six(sleeper_projection("1"), sleeper_projection("2", ppr=0, half_ppr=0, std=0)),
    )

    assert set(stored_ppr(db_session, DAY_ONE)) == {"1"}


def test_new_snapshot_date_adds_rows_and_keeps_the_earlier_day(db_session: Session) -> None:
    ingest(db_session, week_six(sleeper_projection("1", ppr=12.0)), snapshot_date=DAY_ONE)

    ingest(db_session, week_six(sleeper_projection("1", ppr=15.5)), snapshot_date=DAY_TWO)

    assert (stored_ppr(db_session, DAY_ONE), stored_ppr(db_session, DAY_TWO)) == (
        {"1": 12.0},
        {"1": 15.5},
    )


def test_rerun_of_one_week_leaves_other_weeks_of_that_day_alone(db_session: Session) -> None:
    fake = FakeSleeper(
        {
            projections_path(SEASON, 6): [sleeper_projection("1")],
            projections_path(SEASON, 7): [sleeper_projection("1", week=7, ppr=20.0)],
        }
    )
    ingest(db_session, fake, weeks=[6, 7])

    ingest(db_session, fake, weeks=[6])

    assert stored_ppr(db_session, DAY_ONE, week=7) == {"1": 20.0}


def test_week_sleeper_returns_nothing_for_keeps_the_rows_already_stored(
    db_session: Session,
) -> None:
    ingest(db_session, week_six(sleeper_projection("1", ppr=12.0)))

    ingest(db_session, week_six())  # an empty list: a Sleeper hiccup, not "nobody plays"

    assert stored_ppr(db_session, DAY_ONE) == {"1": 12.0}


def test_player_listed_twice_in_one_week_is_stored_once(db_session: Session) -> None:
    # Without de-duplication Postgres rejects the whole upsert ("cannot affect row a
    # second time").
    ingest(db_session, week_six(sleeper_projection("1"), sleeper_projection("1")))

    assert list(stored_ppr(db_session, DAY_ONE)) == ["1"]


def test_more_rows_than_one_statement_holds_are_all_written(db_session: Session) -> None:
    how_many = ROWS_PER_STATEMENT + 1  # one full statement and a partial one
    ingest(db_session, week_six(*(sleeper_projection(str(number)) for number in range(how_many))))

    assert len(stored_ppr(db_session, DAY_ONE)) == how_many
