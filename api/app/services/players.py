from typing import Literal

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.db.models import Player
from app.valuation.formats import VALUED_POSITIONS

SEARCH_ESCAPE = "\\"


def search_players(
    session: Session,
    query: str,
    *,
    position: Literal["QB", "RB", "WR", "TE"] | None = None,
    limit: int = 20,
) -> list[Player]:
    """Players whose name contains `query` (case-insensitive), best matches first.

    Only QB/RB/WR/TE on an NFL team are searchable: those are the players the value model
    covers, and the dump from Sleeper also holds retired players with no team. Names that
    START with the query rank above names that merely contain it.
    """
    # Escape LIKE wildcards so a user typing "50%" or "a_b" searches for those characters.
    escaped = (
        query.strip()
        .replace(SEARCH_ESCAPE, SEARCH_ESCAPE * 2)
        .replace("%", f"{SEARCH_ESCAPE}%")
        .replace("_", f"{SEARCH_ESCAPE}_")
    )
    positions = [position] if position else list(VALUED_POSITIONS)
    starts_with = Player.full_name.ilike(f"{escaped}%", escape=SEARCH_ESCAPE)
    statement = (
        select(Player)
        .where(
            Player.full_name.ilike(f"%{escaped}%", escape=SEARCH_ESCAPE),
            Player.position.in_(positions),
            Player.team.is_not(None),
        )
        .order_by(case((starts_with, 0), else_=1), Player.full_name, Player.player_id)
        .limit(limit)
    )
    return list(session.scalars(statement))
