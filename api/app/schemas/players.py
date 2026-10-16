from pydantic import BaseModel


class PlayerRef(BaseModel):
    """The few fields every list of players needs to display one."""

    player_id: str
    name: str
    position: str
    team: str | None


class PlayerSearchResponse(BaseModel):
    players: list[PlayerRef]
