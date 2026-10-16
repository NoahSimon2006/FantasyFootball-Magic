from datetime import date
from typing import Literal

from pydantic import BaseModel


class LineupOut(BaseModel):
    """Starting slots per team, by Sleeper slot code, e.g. {"QB": 1, "FLEX": 1}."""

    slots: dict[str, int]


class ModelParameters(BaseModel):
    depth_decay: float  # each extra piece on a trade side counts this much of the one before
    even_threshold: float  # gaps within this share of the larger side are "too close to call"
    last_fantasy_week: int  # projections are summed through this NFL week
    valued_positions: list[str]
    default_teams: int
    default_ppr: float
    lineup_1qb: LineupOut
    lineup_superflex: LineupOut


class DataFreshness(BaseModel):
    latest_projection_snapshot: date | None
    projection_snapshots: int  # distinct snapshot days stored (history for "trending")
    players: int
    leagues: int
    trades: int


class MethodologyResponse(BaseModel):
    """The model's real settings and the data behind it, so the methodology page can never
    describe numbers the code doesn't use."""

    model: Literal["projection_vor_v0"]
    parameters: ModelParameters
    data: DataFreshness
