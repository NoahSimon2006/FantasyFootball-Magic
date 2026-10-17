"""Trending players: who is being traded more, and whose projected value moved.

Two independent signals:
- Trade volume: distinct redraft trades a player appeared in during the last N days,
  shown next to the N days before, so "rising" is a measured change.
- Value moves: v0 value from the newest projection snapshot against the snapshot from
  about N days earlier, both valued over the SAME remaining weeks.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import League, Player, ProjectionSnapshot, Trade, TradeAsset
from app.services.values import ValuesResult, compute_values
from app.valuation.formats import LeagueFormat

# A projected-points change smaller than this (over the whole rest of the season) is noise,
# not a mover: Sleeper nudges projections by a fraction of a point all the time.
MIN_POINTS_MOVE = 0.5


@dataclass(frozen=True)
class TradeVolume:
    player_id: str
    trades: int  # distinct trades including the player in the recent window
    previous_trades: int  # the same count for the window before it


@dataclass(frozen=True)
class ValueMove:
    player_id: str
    value_now: float
    value_then: float
    ros_now: float
    ros_then: float

    @property
    def change(self) -> float:
        """Change in value. Includes the effect of the position's replacement level moving:
        when it rises, every player at that position loses value without changing at all."""
        return self.value_now - self.value_then

    @property
    def matters_for_trades(self) -> bool:
        """True when the player is worth more than a free agent in at least one snapshot.
        A player below replacement level both before and after has no trade value either
        way, so his projection change is waiver-wire news, not trade news."""
        return max(self.value_now, self.value_then) > 0

    @property
    def points_change(self) -> float:
        """Change in the player's OWN projected rest-of-season points. This is what risers and
        fallers are ranked by, because it can't be caused by anyone else's projection."""
        return self.ros_now - self.ros_then


def trade_volume(session: Session, *, now: datetime, days: int) -> list[TradeVolume]:
    """Players ranked by how many redraft trades they appeared in over the last `days` days.

    Only league_type 0 (redraft) trades count, since dynasty trading follows different
    logic. Each trade counts once per player however many assets moved. Players seen only
    in the earlier window are included (with `trades=0`) so falling interest is visible too.
    """
    recent_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=2 * days)
    in_recent = Trade.created_at >= recent_start
    rows = session.execute(
        select(
            TradeAsset.player_id,
            func.count(func.distinct(Trade.transaction_id)).filter(in_recent),
            func.count(func.distinct(Trade.transaction_id)).filter(~in_recent),
        )
        .join(Trade, Trade.transaction_id == TradeAsset.transaction_id)
        .join(League, League.league_id == Trade.league_id)
        .where(
            League.league_type == 0,
            TradeAsset.asset_type == "player",
            Trade.created_at >= previous_start,
            Trade.created_at < now,
        )
        .group_by(TradeAsset.player_id)
    ).all()
    volumes = [
        TradeVolume(player_id=player_id, trades=recent, previous_trades=previous)
        for player_id, recent, previous in rows
        if player_id is not None
    ]
    # Most-traded first; ties broken by the earlier window, then id, so order is stable.
    volumes.sort(key=lambda v: (-v.trades, -v.previous_trades, v.player_id))
    return volumes


@dataclass(frozen=True)
class ValueMoves:
    now: ValuesResult
    compared_to: date  # the older snapshot the moves are measured against
    moves: list[ValueMove]  # biggest change in projected points first, in either direction
    players: dict[str, Player]  # rows for every player in `moves`, for names and teams


def value_moves(session: Session, fmt: LeagueFormat, *, days: int) -> ValueMoves | None:
    """How each player's v0 value changed since the snapshot from about `days` days ago.

    Returns None when history is too short: no snapshot at least `days` days older than the
    newest one. Showing "movers" from a one-day gap would be noise, not a trend.
    Both snapshots are valued over the same remaining weeks (the newer one's), so a player
    doesn't "lose value" merely because a week of games was played in between.
    """
    now = compute_values(session, fmt)
    then_date = session.scalar(
        select(func.max(ProjectionSnapshot.snapshot_date)).where(
            ProjectionSnapshot.snapshot_date <= now.snapshot_date - timedelta(days=days)
        )
    )
    if then_date is None:
        return None
    then = compute_values(session, fmt, snapshot_date=then_date, from_week=now.from_week)

    moves: list[ValueMove] = []
    for player_id in now.values.keys() | then.values.keys():
        current = now.values.get(player_id)
        earlier = then.values.get(player_id)
        moves.append(
            ValueMove(
                player_id=player_id,
                value_now=current.value if current else 0.0,
                value_then=earlier.value if earlier else 0.0,
                ros_now=current.ros_points if current else 0.0,
                ros_then=earlier.ros_points if earlier else 0.0,
            )
        )
    moves.sort(key=lambda move: (-abs(move.points_change), move.player_id))
    return ValueMoves(
        now=now, compared_to=then_date, moves=moves, players={**then.players, **now.players}
    )
