from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.db.models import Player
from app.deps import DbSession
from app.routers.values import format_out
from app.schemas.players import PlayerRef
from app.schemas.trending import TradedPlayerOut, TrendingResponse, ValueMoveOut
from app.services.trending import ValueMove, trade_volume, value_moves
from app.services.values import ValuesUnavailableError, latest_snapshot_date, league_format

router = APIRouter(tags=["trending"])


def player_ref(player: Player | None, player_id: str) -> PlayerRef:
    """Display fields for a player; falls back to the id if the player row is missing."""
    if player is None:
        return PlayerRef(player_id=player_id, name=player_id, position="", team=None)
    return PlayerRef(
        player_id=player_id, name=player.full_name, position=player.position or "", team=player.team
    )


def move_out(move: ValueMove, players: dict[str, Player]) -> ValueMoveOut:
    return ValueMoveOut(
        player=player_ref(players.get(move.player_id), move.player_id),
        value_now=round(move.value_now, 2),
        value_then=round(move.value_then, 2),
        change=round(move.change, 2),
        ros_points_now=round(move.ros_now, 2),
        ros_points_then=round(move.ros_then, 2),
    )


@router.get("/trending", response_model=TrendingResponse)
def trending(
    db: DbSession,
    days: Annotated[int, Query(ge=1, le=30)] = 7,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    teams: Annotated[int, Query(ge=2, le=32)] = 12,
    ppr: Annotated[float, Query(ge=0.0, le=1.0)] = 1.0,
    superflex: bool = False,
) -> TrendingResponse:
    """Most-traded players, plus biggest risers and fallers in projected value."""
    fmt = league_format(teams=teams, ppr=ppr, superflex=superflex)
    volumes = trade_volume(db, now=datetime.now(UTC), days=days)[:limit]
    traded_ids = [volume.player_id for volume in volumes]
    traded_players = {
        player.player_id: player
        for player in db.scalars(select(Player).where(Player.player_id.in_(traded_ids)))
    }

    # snapshot_date is the newest projections snapshot whenever one exists, even while the
    # history is too short for movers, so the page can tell "nothing loaded yet" (null) from
    # "history still building" (a date, with compared_to null) without a second request.
    snapshot_date: date | None = None
    compared_to: date | None = None
    try:
        snapshot_date = latest_snapshot_date(db)
        moves = value_moves(db, fmt, days=days)
    except ValuesUnavailableError:
        moves = None  # no projections yet: trade volume still works, value moves don't
    risers: list[ValueMoveOut] = []
    fallers: list[ValueMoveOut] = []
    if moves is not None:
        compared_to = moves.compared_to
        risers = [move_out(m, moves.players) for m in moves.moves if m.change > 0][:limit]
        fallers = [move_out(m, moves.players) for m in moves.moves if m.change < 0][:limit]
        risers.sort(key=lambda m: (-m.change, m.player.player_id))
        fallers.sort(key=lambda m: (m.change, m.player.player_id))

    return TrendingResponse(
        days=days,
        league_format=format_out(fmt),
        most_traded=[
            TradedPlayerOut(
                player=player_ref(traded_players.get(v.player_id), v.player_id),
                trades=v.trades,
                previous_trades=v.previous_trades,
                change=v.trades - v.previous_trades,
            )
            for v in volumes
        ],
        snapshot_date=snapshot_date,
        compared_to=compared_to,
        risers=risers,
        fallers=fallers,
    )
