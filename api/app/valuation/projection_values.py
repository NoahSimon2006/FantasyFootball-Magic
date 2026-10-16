"""Value model v0: rest-of-season projected points over replacement (VOR).

A player's value is how many more fantasy points he should score from now to the end of the
season than the best player a team could pick up for free at his position. This baseline
uses projections only; v1 will learn values from real accepted trades and be backtested
against this one.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.valuation.formats import SLOT_ELIGIBILITY, VALUED_POSITIONS, LeagueFormat


@dataclass(frozen=True)
class WeeklyProjection:
    """One player's projected points for one week, in the three formats Sleeper provides."""

    player_id: str
    week: int
    pts_ppr: float
    pts_half_ppr: float
    pts_std: float


@dataclass(frozen=True)
class PlayerValue:
    player_id: str
    position: str
    ros_points: float  # projected rest-of-season points in the league's scoring
    replacement_points: float  # ros_points of the best free-agent-level player at the position
    value: float  # ros_points - replacement_points, never below 0
    overall_rank: int  # 1 = most valuable player in the format
    position_rank: int  # 1 = most valuable at his position


def points_for_format(projection: WeeklyProjection, ppr: float) -> float:
    """Projected points under any points-per-reception setting.

    Sleeper's PPR and standard projections differ only by receptions x 1 point, so
    `pts_std + ppr * (pts_ppr - pts_std)` is exact for any reception value (0.5 gives
    half-PPR, 0.25 a quarter point per catch, and so on).
    """
    return projection.pts_std + ppr * (projection.pts_ppr - projection.pts_std)


def ros_points(
    projections: Iterable[WeeklyProjection], *, ppr: float, from_week: int, through_week: int
) -> dict[str, float]:
    """Sum each player's projected points over the weeks still to be played, inclusive."""
    totals: dict[str, float] = {}
    for projection in projections:
        if from_week <= projection.week <= through_week:
            totals[projection.player_id] = totals.get(projection.player_id, 0.0) + (
                points_for_format(projection, ppr)
            )
    return totals


def replacement_levels(
    ros: Mapping[str, float], positions: Mapping[str, str], fmt: LeagueFormat
) -> dict[str, float]:
    """Rest-of-season points of the best player at each position who wouldn't start anywhere.

    Simulates every team filling its starting lineup from one shared pool: slots that accept
    the fewest positions are filled first (QB, RB, WR, TE), then FLEX-style slots take the
    best players left among their eligible positions, then SUPER_FLEX. Whoever is left is
    "replacement level": the free-agent alternative a trade has to beat. This is why
    superflex raises QB values: the extra slot consumes more QBs, so the best leftover QB
    is worse, and every starting QB's edge over him grows.
    """
    pools: dict[str, list[float]] = {position: [] for position in VALUED_POSITIONS}
    for player_id, points in ros.items():
        position = positions.get(player_id)
        if position in pools:
            pools[position].append(points)
    for points_list in pools.values():
        points_list.sort(reverse=True)
    next_index = dict.fromkeys(VALUED_POSITIONS, 0)

    def best_available(position: str) -> float | None:
        index = next_index[position]
        pool = pools[position]
        return pool[index] if index < len(pool) else None

    slot_order = sorted(fmt.slots, key=lambda slot: (len(SLOT_ELIGIBILITY[slot]), slot))
    for slot in slot_order:
        eligible = [p for p in SLOT_ELIGIBILITY[slot] if p in pools]
        for _ in range(fmt.slots[slot] * fmt.teams):
            candidates: list[tuple[float, str]] = []
            for position in eligible:
                available = best_available(position)
                if available is not None:
                    candidates.append((available, position))
            if not candidates:
                break
            _, chosen_position = max(candidates)
            next_index[chosen_position] += 1

    return {position: best_available(position) or 0.0 for position in VALUED_POSITIONS}


def player_values(
    ros: Mapping[str, float], positions: Mapping[str, str], fmt: LeagueFormat
) -> dict[str, PlayerValue]:
    """VOR for every player with a valued position (QB/RB/WR/TE), ranked within the format.

    Players at other positions (K, DEF) or with an unknown position are left out; callers
    treat missing players as unknown rather than worthless.
    """
    replacement = replacement_levels(ros, positions, fmt)
    rows = []
    for player_id, points in ros.items():
        position = positions.get(player_id)
        if position not in replacement:
            continue
        value = max(0.0, points - replacement[position])
        rows.append((player_id, position, points, replacement[position], value))

    # Deterministic order: value, then raw points, then id, so equal players rank stably.
    rows.sort(key=lambda row: (-row[4], -row[2], row[0]))
    position_counts: dict[str, int] = {}
    values: dict[str, PlayerValue] = {}
    for overall_rank, (player_id, position, points, repl, value) in enumerate(rows, start=1):
        position_counts[position] = position_counts.get(position, 0) + 1
        values[player_id] = PlayerValue(
            player_id=player_id,
            position=position,
            ros_points=points,
            replacement_points=repl,
            value=value,
            overall_rank=overall_rank,
            position_rank=position_counts[position],
        )
    return values
