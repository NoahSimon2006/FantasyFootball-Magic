import pytest

from app.services.explain import build_drivers
from app.valuation.trade import evaluate_trade

VALUES = {"star": 50.0, "mid1": 30.0, "mid2": 30.0, "near_mid": 29.0}


def test_a_clear_winner_gets_a_value_gap_driver_naming_the_team() -> None:
    drivers = build_drivers(evaluate_trade(["star"], ["mid1"], VALUES))

    assert [(d.kind, d.side, d.amount) for d in drivers] == [("value_gap", "a", 20.0)]
    assert drivers[0].label == "Team A receives 20.0 more value points (40% of the larger side)"


def test_the_winner_can_be_team_b() -> None:
    drivers = build_drivers(evaluate_trade(["mid1"], ["star"], VALUES))

    assert (drivers[0].kind, drivers[0].side) == ("value_gap", "b")


def test_an_even_trade_says_too_close_to_call() -> None:
    drivers = build_drivers(evaluate_trade(["mid1"], ["near_mid"], VALUES))

    assert [(d.kind, d.side) for d in drivers] == [("value_gap", None)]
    assert drivers[0].label.startswith("Too close to call")


def test_extra_players_show_their_depth_discount_as_its_own_driver() -> None:
    drivers = build_drivers(evaluate_trade(["star"], ["mid1", "mid2"], VALUES))

    depth = [d for d in drivers if d.kind == "depth_adjustment"]
    # Team B's second piece counts 85%: 30 + 30 = 60 raw vs 55.5 adjusted, so 4.5 discounted.
    assert [(d.side, d.amount) for d in depth] == [("b", 4.5)]
    assert "Team B's 2 players" in depth[0].label


def test_a_one_for_one_trade_has_no_depth_driver() -> None:
    drivers = build_drivers(evaluate_trade(["star"], ["mid1"], VALUES))

    assert all(d.kind != "depth_adjustment" for d in drivers)


@pytest.mark.parametrize("receives", [["mid1", "mid2"], ["star", "mid1"]])
def test_both_sides_can_carry_a_depth_driver(receives: list[str]) -> None:
    drivers = build_drivers(evaluate_trade(receives, ["star", "near_mid", "mid1"], VALUES))

    sides = sorted(d.side or "" for d in drivers if d.kind == "depth_adjustment")
    assert sides == ["a", "b"]
