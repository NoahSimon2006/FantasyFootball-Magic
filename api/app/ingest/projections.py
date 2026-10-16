"""Store dated snapshots of Sleeper's weekly projections in `projection_snapshots`.

Each run saves what the projections said on `snapshot_date`. Rows from earlier dates are
never touched, so the table builds a history: "projection movers" compares one day's
snapshot of a week with an earlier day's.
"""

import logging
from collections.abc import Sequence
from datetime import date
from itertools import batched

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import ProjectionSnapshot
from app.sleeper.client import SleeperClient
from app.sleeper.models import ProjectionRow

logger = logging.getLogger(__name__)

# Rows per INSERT. A week has a few hundred rows; this caps any single statement anyway.
ROWS_PER_STATEMENT = 1000


def ingest_projections(
    session: Session,
    client: SleeperClient,
    *,
    season: int,
    weeks: Sequence[int],
    snapshot_date: date,
) -> int:
    """Snapshot each week's projections under `snapshot_date`; return the rows written.

    Running again on the same `snapshot_date` replaces that day's snapshot of each week:
    the day's rows for the week are deleted, then the fresh rows are upserted, all inside
    the caller's transaction. A plain upsert would overwrite the players fetched again but
    would keep a stale row for anyone who dropped out of the projections since the earlier
    run (for example, a player ruled out on game day). A different `snapshot_date` adds new
    rows and leaves every other day as it was.

    Skipped rows:
    - Rows whose PPR, half-PPR, and standard points are all 0. Sleeper also lists players
      with nothing projected that week (on bye, injured, inactive). For the value model and
      for "projection movers" those rows are noise. So in a snapshot that has rows for a
      week, a player missing from that week was projected for 0.
    - A week Sleeper returned no rows for at all. That looks like a hiccup on Sleeper's
      side, not a real "nobody plays", so the week's existing rows for the day are kept and
      a warning is logged.

    The caller owns the transaction: nothing here commits.
    """
    written = 0
    for week in weeks:
        fetched = client.get_weekly_projections(season, week)
        if not fetched:
            logger.warning(
                "Sleeper returned no projections for %d week %d; keeping any rows already "
                "stored for that week on %s",
                season,
                week,
                snapshot_date,
            )
            continue
        rows = _rows(fetched, snapshot_date=snapshot_date, season=season, week=week)
        session.execute(
            delete(ProjectionSnapshot).where(
                ProjectionSnapshot.snapshot_date == snapshot_date,
                ProjectionSnapshot.season == season,
                ProjectionSnapshot.week == week,
            )
        )
        for batch in batched(rows, ROWS_PER_STATEMENT, strict=False):  # last batch may be short
            statement = insert(ProjectionSnapshot).values(list(batch))
            # The delete above already cleared this day's rows. The conflict clause covers a
            # second run of the same day that commits in the meantime.
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["snapshot_date", "season", "week", "player_id"],
                    set_={
                        "pts_ppr": statement.excluded.pts_ppr,
                        "pts_half_ppr": statement.excluded.pts_half_ppr,
                        "pts_std": statement.excluded.pts_std,
                    },
                )
            )
        logger.info(
            "Projections %d week %d: stored %d players, skipped %d with no projected points",
            season,
            week,
            len(rows),
            len(fetched) - len(rows),
        )
        written += len(rows)
    return written


def _rows(
    fetched: Sequence[ProjectionRow], *, snapshot_date: date, season: int, week: int
) -> list[dict[str, object]]:
    """One row per player with projected points, keyed by the week that was requested."""
    rows: dict[str, dict[str, object]] = {}
    for projection in fetched:
        if not (projection.pts_ppr or projection.pts_half_ppr or projection.pts_std):
            continue  # all three are 0: see "Skipped rows" in ingest_projections
        # setdefault keeps one row per player. Postgres rejects an upsert that names the same
        # key twice ("cannot affect row a second time"), so one duplicate in Sleeper's list
        # would otherwise fail the whole week.
        rows.setdefault(
            projection.player_id,
            {
                "snapshot_date": snapshot_date,
                "season": season,
                "week": week,
                "player_id": projection.player_id,
                "pts_ppr": projection.pts_ppr,
                "pts_half_ppr": projection.pts_half_ppr,
                "pts_std": projection.pts_std,
            },
        )
    return list(rows.values())
