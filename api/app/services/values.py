"""Compute v0 player values from the latest projection snapshot in the database.

The I/O lives here; the math lives in `app.valuation` (pure), so the math stays testable
without a database and this layer stays thin.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Player, ProjectionSnapshot
from app.valuation.formats import STANDARD_1QB, STANDARD_SUPERFLEX, LeagueFormat
from app.valuation.projection_values import (
    PlayerValue,
    WeeklyProjection,
    player_values,
    ros_points,
)
from app.valuation.trade import UnknownPlayerError

# Most fantasy leagues finish their championship in NFL week 17; week 18 is usually unused.
LAST_FANTASY_WEEK = 17


class ValuesUnavailableError(Exception):
    """No projections have been ingested yet, so there is nothing to value."""


def league_format(*, teams: int, ppr: float, superflex: bool) -> LeagueFormat:
    """Sleeper's standard lineup (plus a SUPER_FLEX slot when asked) for `teams` teams."""
    base = STANDARD_SUPERFLEX if superflex else STANDARD_1QB
    return LeagueFormat(teams=teams, ppr=ppr, slots=base.slots)


@dataclass(frozen=True)
class ValuesResult:
    snapshot_date: date
    season: int
    from_week: int
    through_week: int
    values: dict[str, PlayerValue]  # player_id -> value, valued positions only
    players: dict[str, Player]  # player_id -> player row (names, teams) for display


def latest_snapshot_date(session: Session) -> date:
    snapshot_date: date | None = session.scalar(select(func.max(ProjectionSnapshot.snapshot_date)))
    if snapshot_date is None:
        raise ValuesUnavailableError("no projection snapshots yet; run the projections ingest")
    return snapshot_date


def compute_values(
    session: Session,
    fmt: LeagueFormat,
    *,
    snapshot_date: date | None = None,
    from_week: int | None = None,
) -> ValuesResult:
    """Values for every projected QB/RB/WR/TE under `fmt`.

    Uses the newest snapshot unless `snapshot_date` names another. The snapshot's earliest
    week is treated as the current week (the projections ingest stores weeks from "now"
    through the end of the season). Passing `from_week` values an older snapshot over the
    same remaining weeks as a newer one: without that, every player would look like he lost
    value between snapshots just because a week of games was used up.
    """
    if snapshot_date is None:
        snapshot_date = latest_snapshot_date(session)
    rows = session.scalars(
        select(ProjectionSnapshot).where(ProjectionSnapshot.snapshot_date == snapshot_date)
    ).all()
    if not rows:
        raise ValuesUnavailableError(f"no projections in the {snapshot_date} snapshot")
    season = max(row.season for row in rows)
    rows = [row for row in rows if row.season == season]
    if from_week is None:
        from_week = min(row.week for row in rows)

    projections = [
        WeeklyProjection(
            player_id=row.player_id,
            week=row.week,
            pts_ppr=row.pts_ppr,
            pts_half_ppr=row.pts_half_ppr,
            pts_std=row.pts_std,
        )
        for row in rows
    ]
    totals = ros_points(
        projections, ppr=fmt.ppr, from_week=from_week, through_week=LAST_FANTASY_WEEK
    )
    players = {
        player.player_id: player
        for player in session.scalars(select(Player).where(Player.player_id.in_(list(totals))))
    }
    positions = {player_id: player.position or "" for player_id, player in players.items()}
    return ValuesResult(
        snapshot_date=snapshot_date,
        season=season,
        from_week=from_week,
        through_week=LAST_FANTASY_WEEK,
        values=player_values(totals, positions, fmt),
        players=players,
    )


def players_for_trade(
    session: Session, result: ValuesResult, player_ids: list[str]
) -> tuple[dict[str, float], dict[str, Player]]:
    """Values and player rows for every id in a trade.

    A player we know but who has no projection (out for the season, a kicker) is worth 0:
    that's a real projection of nothing. An id that isn't a known player raises
    UnknownPlayerError instead, so a typo can never quietly count as a worthless player.
    """
    players = {pid: result.players[pid] for pid in player_ids if pid in result.players}
    missing = [pid for pid in player_ids if pid not in players]
    if missing:
        for player in session.scalars(select(Player).where(Player.player_id.in_(missing))):
            players[player.player_id] = player
    unknown = [pid for pid in player_ids if pid not in players]
    if unknown:
        raise UnknownPlayerError(unknown)
    values = {pid: result.values[pid].value if pid in result.values else 0.0 for pid in player_ids}
    return values, players
