from fastapi import APIRouter

from app.deps import DbSession
from app.errors import ApiError
from app.routers.values import format_out, player_value_out, values_or_503
from app.schemas.trades import TradeEvaluateRequest, TradeEvaluationResponse, TradeSideOut
from app.services.explain import build_drivers
from app.services.values import league_format, players_for_trade
from app.valuation.trade import SideValue, UnknownPlayerError, evaluate_trade

router = APIRouter(tags=["trades"])


@router.post("/trades/evaluate", response_model=TradeEvaluationResponse)
def evaluate(body: TradeEvaluateRequest, db: DbSession) -> TradeEvaluationResponse:
    """Who wins a trade under v0 values, and by how much."""
    fmt = league_format(teams=body.teams, ppr=body.ppr, superflex=body.superflex)
    result = values_or_503(db, fmt)
    try:
        values, players = players_for_trade(db, result, [*body.receives_a, *body.receives_b])
    except UnknownPlayerError as exc:
        raise ApiError(404, "PLAYER_NOT_FOUND", str(exc)) from exc
    evaluation = evaluate_trade(body.receives_a, body.receives_b, values)

    def side_out(side: SideValue) -> TradeSideOut:
        return TradeSideOut(
            players=[
                player_value_out(players[pid], result.values.get(pid)) for pid in side.player_ids
            ],
            raw_total=round(side.raw_total, 2),
            adjusted_total=round(side.adjusted_total, 2),
        )

    return TradeEvaluationResponse(
        side_a=side_out(evaluation.side_a),
        side_b=side_out(evaluation.side_b),
        verdict=evaluation.verdict,
        margin=round(evaluation.margin, 2),
        margin_share=round(evaluation.margin_share, 4),
        drivers=build_drivers(evaluation),
        method="projection_vor_v0",
        snapshot_date=result.snapshot_date,
        league_format=format_out(fmt),
    )
