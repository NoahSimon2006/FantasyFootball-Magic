from datetime import date

from pydantic import BaseModel

from app.schemas.players import PlayerRef
from app.schemas.values import LeagueFormatOut


class TradedPlayerOut(BaseModel):
    player: PlayerRef
    trades: int  # redraft trades including this player in the recent window
    previous_trades: int  # the same count for the window before it
    change: int  # trades - previous_trades


class ValueMoveOut(BaseModel):
    player: PlayerRef
    value_now: float
    value_then: float
    change: float  # value_now - value_then
    ros_points_now: float
    ros_points_then: float


class TrendingResponse(BaseModel):
    days: int  # the window length used for both signals
    league_format: LeagueFormatOut
    most_traded: list[TradedPlayerOut]
    # Value moves need projection snapshots at least `days` apart. Until then risers and
    # fallers are empty and `compared_to` is null, so the page can say so instead of showing
    # noise. `snapshot_date` is the newest snapshot whenever projections exist at all (null
    # only when none have been loaded), so the two empty states can be told apart.
    snapshot_date: date | None
    compared_to: date | None
    risers: list[ValueMoveOut]
    fallers: list[ValueMoveOut]
