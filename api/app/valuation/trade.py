"""Trade evaluation: which side gets more value, and by how much.

v0 sums each side's player values with a depth discount. Summing alone would say two
decent players always beat one star, but in a real lineup the two pieces compete for the
slots one star fills, and the team receiving more players must cut someone to make room.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

# Each additional piece on a side counts this much of the piece before it (sorted by value):
# 1st at 100%, 2nd at 85%, 3rd at 72%, ... A 1-for-1 trade is unaffected. This is a
# hand-picked placeholder; value model v1 will fit it from real accepted trades.
DEPTH_DECAY = 0.85

# A trade is "even" when the smaller side is within this share of the larger side.
EVEN_THRESHOLD = 0.05

Verdict = Literal["a", "b", "even"]


class UnknownPlayerError(ValueError):
    """A trade mentions a player the model has no value for. We never value unknowns at 0:
    a typo'd id would silently make a trade look lopsided."""

    def __init__(self, player_ids: Sequence[str]) -> None:
        self.player_ids = list(player_ids)
        super().__init__(f"no value for player id(s): {', '.join(self.player_ids)}")


@dataclass(frozen=True)
class SideValue:
    player_ids: tuple[str, ...]
    raw_total: float  # plain sum of player values
    adjusted_total: float  # after the depth discount; this is what decides the verdict


@dataclass(frozen=True)
class TradeEvaluation:
    side_a: SideValue  # what team A RECEIVES
    side_b: SideValue  # what team B RECEIVES
    verdict: Verdict  # which team receives more value, or "even"
    margin: float  # |a - b| in adjusted value points
    margin_share: float  # margin as a share of the larger side, 0.0 to 1.0


def side_value(
    player_ids: Sequence[str], values: Mapping[str, float], *, depth_decay: float = DEPTH_DECAY
) -> SideValue:
    """Value of one side of a trade; raises UnknownPlayerError for players without a value."""
    missing = [player_id for player_id in player_ids if player_id not in values]
    if missing:
        raise UnknownPlayerError(missing)
    ordered = sorted((values[player_id] for player_id in player_ids), reverse=True)
    adjusted = sum(value * depth_decay**index for index, value in enumerate(ordered))
    return SideValue(player_ids=tuple(player_ids), raw_total=sum(ordered), adjusted_total=adjusted)


def evaluate_trade(
    receives_a: Sequence[str],
    receives_b: Sequence[str],
    values: Mapping[str, float],
    *,
    depth_decay: float = DEPTH_DECAY,
    even_threshold: float = EVEN_THRESHOLD,
) -> TradeEvaluation:
    """Compare what team A receives with what team B receives.

    The verdict names the team that receives more adjusted value, or "even" when the gap is
    within `even_threshold` of the larger side (small gaps are inside the model's noise).
    """
    unknown = [p for p in [*receives_a, *receives_b] if p not in values]
    if unknown:
        raise UnknownPlayerError(unknown)
    side_a = side_value(receives_a, values, depth_decay=depth_decay)
    side_b = side_value(receives_b, values, depth_decay=depth_decay)
    a, b = side_a.adjusted_total, side_b.adjusted_total
    margin = abs(a - b)
    larger = max(a, b)
    margin_share = margin / larger if larger > 0 else 0.0
    verdict: Verdict
    if margin_share <= even_threshold:
        verdict = "even"
    else:
        verdict = "a" if a > b else "b"
    return TradeEvaluation(
        side_a=side_a, side_b=side_b, verdict=verdict, margin=margin, margin_share=margin_share
    )
