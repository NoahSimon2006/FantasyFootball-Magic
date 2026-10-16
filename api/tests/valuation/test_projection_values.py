"""Value model v0 on a tiny league whose answers can be worked out on paper.

The league: 2 teams, each starting QB, RB, WR, and one FLEX (RB/WR/TE). Rest-of-season
points (ROS) per player:

    QB  a=100  b=90  c=80  d=40
    RB  r1=95  r2=85  r3=70  r4=60
    WR  w1=92  w2=75  w3=65  w4=50

Lineup fill: QB slots take a, b; RB slots r1, r2; WR slots w1, w2; the two FLEX slots take
the best leftovers, r3 (70) then w3 (65 beats r4's 60). Best leftovers per position are the
replacement levels: QB c=80, RB r4=60, WR w4=50, TE none = 0.
"""

from types import MappingProxyType

import pytest

from app.valuation.formats import LeagueFormat
from app.valuation.projection_values import (
    WeeklyProjection,
    player_values,
    points_for_format,
    replacement_levels,
    ros_points,
)

ROS = {
    "a": 100.0, "b": 90.0, "c": 80.0, "d": 40.0,
    "r1": 95.0, "r2": 85.0, "r3": 70.0, "r4": 60.0,
    "w1": 92.0, "w2": 75.0, "w3": 65.0, "w4": 50.0,
}  # fmt: skip
POSITIONS = {
    **dict.fromkeys(["a", "b", "c", "d"], "QB"),
    **dict.fromkeys(["r1", "r2", "r3", "r4"], "RB"),
    **dict.fromkeys(["w1", "w2", "w3", "w4"], "WR"),
}

TINY_1QB = LeagueFormat(teams=2, slots=MappingProxyType({"QB": 1, "RB": 1, "WR": 1, "FLEX": 1}))
TINY_SUPERFLEX = LeagueFormat(
    teams=2, slots=MappingProxyType({"QB": 1, "RB": 1, "WR": 1, "FLEX": 1, "SUPER_FLEX": 1})
)


def make_projection(week: int, std: float, ppr: float, player_id: str = "p1") -> WeeklyProjection:
    half = std + 0.5 * (ppr - std)
    return WeeklyProjection(player_id, week, pts_ppr=ppr, pts_half_ppr=half, pts_std=std)


@pytest.mark.parametrize(
    ("ppr", "expected"), [(1.0, 15.0), (0.5, 12.5), (0.0, 10.0), (0.25, 11.25)]
)
def test_points_for_format_scales_receptions_for_any_ppr_setting(
    ppr: float, expected: float
) -> None:
    projection = make_projection(week=6, std=10.0, ppr=15.0)  # 5 projected catches

    assert points_for_format(projection, ppr) == pytest.approx(expected)


def test_half_ppr_formula_matches_sleepers_half_ppr_number() -> None:
    projection = make_projection(week=6, std=8.2, ppr=13.6)

    assert points_for_format(projection, 0.5) == pytest.approx(projection.pts_half_ppr)


def test_ros_points_sums_only_the_remaining_weeks() -> None:
    projections = [
        make_projection(week=5, std=10, ppr=10),  # already played: excluded
        make_projection(week=6, std=10, ppr=12),
        make_projection(week=7, std=10, ppr=14),
        make_projection(week=18, std=10, ppr=16),  # after the fantasy season: excluded
        make_projection(week=6, std=5, ppr=5, player_id="p2"),
    ]

    totals = ros_points(projections, ppr=1.0, from_week=6, through_week=17)

    assert totals == {"p1": pytest.approx(26.0), "p2": pytest.approx(5.0)}


def test_replacement_level_is_the_best_player_left_after_every_lineup_is_filled() -> None:
    levels = replacement_levels(ROS, POSITIONS, TINY_1QB)

    assert levels == {"QB": 80.0, "RB": 60.0, "WR": 50.0, "TE": 0.0}


def test_value_is_points_over_replacement_and_never_negative() -> None:
    values = player_values(ROS, POSITIONS, TINY_1QB)

    assert {pid: v.value for pid, v in values.items()} == {
        "a": 20.0, "b": 10.0, "c": 0.0, "d": 0.0,
        "r1": 35.0, "r2": 25.0, "r3": 10.0, "r4": 0.0,
        "w1": 42.0, "w2": 25.0, "w3": 15.0, "w4": 0.0,
    }  # fmt: skip


def test_ranks_break_value_ties_by_raw_points() -> None:
    values = player_values(ROS, POSITIONS, TINY_1QB)

    # r2 and w2 are both worth 25; r2 projects more raw points (85 vs 75), so ranks first.
    assert (values["r2"].overall_rank, values["w2"].overall_rank) == (3, 4)
    assert values["w1"].overall_rank == 1
    assert [values[p].position_rank for p in ("a", "b", "c", "d")] == [1, 2, 3, 4]


def test_superflex_makes_quarterbacks_much_more_valuable() -> None:
    one_qb = player_values(ROS, POSITIONS, TINY_1QB)
    superflex = player_values(ROS, POSITIONS, TINY_SUPERFLEX)

    # The SUPER_FLEX slots take c (80) and then r4 (60 beats d's 40), so the best leftover
    # QB is d at 40 instead of c at 80, and a's edge grows from 20 to 60 points.
    assert (one_qb["a"].value, superflex["a"].value) == (20.0, 60.0)
    assert replacement_levels(ROS, POSITIONS, TINY_SUPERFLEX)["QB"] == 40.0


def test_kickers_defenses_and_unknown_positions_are_left_out() -> None:
    ros = {**ROS, "k1": 120.0, "def1": 110.0, "mystery": 200.0}
    positions = {**POSITIONS, "k1": "K", "def1": "DEF"}  # "mystery" has no position

    values = player_values(ros, positions, TINY_1QB)

    assert {"k1", "def1", "mystery"}.isdisjoint(values)


def test_a_position_with_no_players_has_zero_replacement_level() -> None:
    levels = replacement_levels({}, {}, TINY_1QB)

    assert levels == {"QB": 0.0, "RB": 0.0, "WR": 0.0, "TE": 0.0}
