from fastapi import APIRouter
from sqlalchemy import distinct, func, select

from app.db.models import League, Player, ProjectionSnapshot, Trade
from app.deps import DbSession
from app.schemas.methodology import (
    DataFreshness,
    LineupOut,
    MethodologyResponse,
    ModelParameters,
)
from app.services.values import LAST_FANTASY_WEEK
from app.valuation.formats import STANDARD_1QB, STANDARD_SUPERFLEX, VALUED_POSITIONS
from app.valuation.trade import DEPTH_DECAY, EVEN_THRESHOLD

router = APIRouter(tags=["methodology"])


@router.get("/methodology", response_model=MethodologyResponse)
def methodology(db: DbSession) -> MethodologyResponse:
    """How values are computed, read straight from the code's constants, plus how much data
    stands behind them right now."""
    latest, snapshot_days = db.execute(
        select(
            func.max(ProjectionSnapshot.snapshot_date),
            func.count(distinct(ProjectionSnapshot.snapshot_date)),
        )
    ).one()
    return MethodologyResponse(
        model="projection_vor_v0",
        parameters=ModelParameters(
            depth_decay=DEPTH_DECAY,
            even_threshold=EVEN_THRESHOLD,
            last_fantasy_week=LAST_FANTASY_WEEK,
            valued_positions=list(VALUED_POSITIONS),
            default_teams=STANDARD_1QB.teams,
            default_ppr=STANDARD_1QB.ppr,
            lineup_1qb=LineupOut(slots=dict(STANDARD_1QB.slots)),
            lineup_superflex=LineupOut(slots=dict(STANDARD_SUPERFLEX.slots)),
        ),
        data=DataFreshness(
            latest_projection_snapshot=latest,
            projection_snapshots=snapshot_days,
            players=db.scalar(select(func.count()).select_from(Player)) or 0,
            leagues=db.scalar(select(func.count()).select_from(League)) or 0,
            trades=db.scalar(select(func.count()).select_from(Trade)) or 0,
        ),
    )
