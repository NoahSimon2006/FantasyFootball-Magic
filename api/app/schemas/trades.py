from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.values import LeagueFormatOut, PlayerValueOut

MAX_PLAYERS_PER_SIDE = 10


class TradeEvaluateRequest(BaseModel):
    """What each team RECEIVES, plus the league format to value it in."""

    receives_a: list[str] = Field(default_factory=list, max_length=MAX_PLAYERS_PER_SIDE)
    receives_b: list[str] = Field(default_factory=list, max_length=MAX_PLAYERS_PER_SIDE)
    teams: int = Field(default=12, ge=2, le=32)
    ppr: float = Field(default=1.0, ge=0.0, le=1.0)
    superflex: bool = False

    @model_validator(mode="after")
    def _each_player_once(self) -> Self:
        for side in (self.receives_a, self.receives_b):
            if len(set(side)) != len(side):
                raise ValueError("a player is listed twice on the same side")
        both = sorted(set(self.receives_a) & set(self.receives_b))
        if both:
            raise ValueError(f"player(s) on both sides of the trade: {', '.join(both)}")
        return self


class TradeSideOut(BaseModel):
    players: list[PlayerValueOut]
    raw_total: float  # plain sum of player values
    adjusted_total: float  # after the depth discount; this decides the verdict


class DriverOut(BaseModel):
    """One reason behind a verdict, with its number. The UI renders these as evidence chips
    and the AI advisor receives the same list, so both always tell the same story."""

    kind: Literal["value_gap", "depth_adjustment"]
    side: Literal["a", "b"] | None  # which team it favors or applies to; None when even
    amount: float  # value points
    label: str  # plain-English sentence for display


class TradeEvaluationResponse(BaseModel):
    side_a: TradeSideOut  # what team A receives
    side_b: TradeSideOut  # what team B receives
    verdict: Literal["a", "b", "even"]  # which team receives more value
    margin: float  # gap in adjusted value points
    margin_share: float  # gap as a share of the larger side, 0 to 1
    drivers: list[DriverOut]
    # How the values were computed. v0 uses projections only, with no trade-market
    # evidence yet; the field exists so the UI and advisor can say so honestly.
    method: Literal["projection_vor_v0"]
    snapshot_date: date
    league_format: LeagueFormatOut
