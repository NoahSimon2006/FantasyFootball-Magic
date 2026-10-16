from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.deps import DbSession
from app.schemas.players import PlayerRef, PlayerSearchResponse
from app.services.players import search_players

router = APIRouter(tags=["players"])


@router.get("/players", response_model=PlayerSearchResponse)
def find_players(
    db: DbSession,
    q: Annotated[str, Query(min_length=2, max_length=50, description="Part of a player's name")],
    position: Literal["QB", "RB", "WR", "TE"] | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> PlayerSearchResponse:
    """Find players by name, for pickers such as the trade calculator."""
    return PlayerSearchResponse(
        players=[
            PlayerRef(
                player_id=player.player_id,
                name=player.full_name,
                position=player.position or "",
                team=player.team,
            )
            for player in search_players(db, q, position=position, limit=limit)
        ]
    )
