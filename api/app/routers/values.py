from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.db.models import Player
from app.deps import DbSession
from app.errors import ApiError
from app.schemas.values import LeagueFormatOut, PlayerValueOut, ValuesResponse
from app.services.values import (
    ValuesResult,
    ValuesUnavailableError,
    compute_values,
    league_format,
)
from app.valuation.formats import LeagueFormat
from app.valuation.projection_values import PlayerValue

router = APIRouter(tags=["values"])


def values_or_503(db: DbSession, fmt: LeagueFormat) -> ValuesResult:
    """Compute values, turning "no projections ingested yet" into a clear 503."""
    try:
        return compute_values(db, fmt)
    except ValuesUnavailableError as exc:
        raise ApiError(503, "VALUES_UNAVAILABLE", str(exc)) from exc


def format_out(fmt: LeagueFormat) -> LeagueFormatOut:
    return LeagueFormatOut(teams=fmt.teams, ppr=fmt.ppr, superflex=fmt.is_superflex)


def player_value_out(player: Player, value: PlayerValue | None) -> PlayerValueOut:
    """API view of one player; `value=None` means known player with no projection (worth 0)."""
    return PlayerValueOut(
        player_id=player.player_id,
        name=player.full_name,
        position=player.position or "",
        team=player.team,
        ros_points=round(value.ros_points, 2) if value else 0.0,
        value=round(value.value, 2) if value else 0.0,
        overall_rank=value.overall_rank if value else None,
        position_rank=value.position_rank if value else None,
    )


@router.get("/values", response_model=ValuesResponse)
def list_values(
    db: DbSession,
    teams: Annotated[int, Query(ge=2, le=32)] = 12,
    ppr: Annotated[float, Query(ge=0.0, le=1.0)] = 1.0,
    superflex: bool = False,
    position: Literal["QB", "RB", "WR", "TE"] | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ValuesResponse:
    """Players ranked by v0 value (projected points over replacement) for a league format."""
    fmt = league_format(teams=teams, ppr=ppr, superflex=superflex)
    result = values_or_503(db, fmt)
    ranked = sorted(result.values.values(), key=lambda value: value.overall_rank)
    if position is not None:
        ranked = [value for value in ranked if value.position == position]
    page = ranked[offset : offset + limit]
    return ValuesResponse(
        snapshot_date=result.snapshot_date,
        season=result.season,
        from_week=result.from_week,
        through_week=result.through_week,
        league_format=format_out(fmt),
        total=len(ranked),
        players=[player_value_out(result.players[v.player_id], v) for v in page],
    )
