from datetime import date

from pydantic import BaseModel


class LeagueFormatOut(BaseModel):
    teams: int
    ppr: float
    superflex: bool


class PlayerValueOut(BaseModel):
    player_id: str
    name: str
    position: str
    team: str | None
    ros_points: float  # projected rest-of-season points in this format
    value: float  # points over replacement level; 0 = waiver-level
    overall_rank: int | None  # None for players the model doesn't rank (e.g. no projection)
    position_rank: int | None


class ValuesResponse(BaseModel):
    snapshot_date: date  # which day's projections these values come from
    season: int
    from_week: int
    through_week: int
    league_format: LeagueFormatOut
    total: int  # players matching the filters, before limit/offset
    players: list[PlayerValueOut]
