"""Turn a trade evaluation into a list of visible reasons ("drivers").

Every adjustment the model makes is listed here with its number, so nothing happens
silently inside a total. The UI and the AI advisor both consume this same list.
"""

from typing import Literal

from app.schemas.trades import DriverOut
from app.valuation.trade import EVEN_THRESHOLD, SideValue, TradeEvaluation

# Below this many points a depth adjustment is rounding noise, not worth a chip.
MIN_DEPTH_DISCOUNT = 0.005


def build_drivers(evaluation: TradeEvaluation) -> list[DriverOut]:
    drivers: list[DriverOut] = []

    match evaluation.verdict:
        case "even":
            drivers.append(
                DriverOut(
                    kind="value_gap",
                    side=None,
                    amount=round(evaluation.margin, 2),
                    label=(
                        f"Too close to call: the gap is {evaluation.margin_share:.1%} of the "
                        f"larger side, under the {EVEN_THRESHOLD:.0%} threshold"
                    ),
                )
            )
        case "a" | "b" as winner:
            drivers.append(
                DriverOut(
                    kind="value_gap",
                    side=winner,
                    amount=round(evaluation.margin, 2),
                    label=(
                        f"Team {winner.upper()} receives {evaluation.margin:.1f} more value "
                        f"points ({evaluation.margin_share:.0%} of the larger side)"
                    ),
                )
            )

    sides: tuple[tuple[Literal["a", "b"], SideValue], ...] = (
        ("a", evaluation.side_a),
        ("b", evaluation.side_b),
    )
    for key, side in sides:
        discount = side.raw_total - side.adjusted_total
        if len(side.player_ids) > 1 and discount > MIN_DEPTH_DISCOUNT:
            drivers.append(
                DriverOut(
                    kind="depth_adjustment",
                    side=key,
                    amount=round(discount, 2),
                    label=(
                        f"Team {key.upper()}'s {len(side.player_ids)} players are discounted "
                        f"by {discount:.1f} points because extra players compete for starting "
                        f"spots"
                    ),
                )
            )
    return drivers
