import pytest

from app.valuation.trade import UnknownPlayerError, evaluate_trade, side_value

VALUES = {"star": 50.0, "mid1": 30.0, "mid2": 30.0, "near_mid": 29.0, "bench": 10.0}


def test_one_for_one_trade_goes_to_the_more_valuable_player() -> None:
    result = evaluate_trade(["star"], ["mid1"], VALUES)

    assert result.verdict == "a"
    assert result.margin == pytest.approx(20.0)
    assert result.margin_share == pytest.approx(0.4)


def test_depth_discount_shrinks_the_two_player_side() -> None:
    # Team B receives 30 + 30 = 60 raw, but the second piece counts 85%: 30 + 25.5 = 55.5.
    result = evaluate_trade(["star"], ["mid1", "mid2"], VALUES)

    assert result.side_b.raw_total == pytest.approx(60.0)
    assert result.side_b.adjusted_total == pytest.approx(55.5)
    assert result.verdict == "b"


def test_a_stronger_depth_discount_flips_a_two_for_one() -> None:
    # At 50%, two 30s are worth 30 + 15 = 45, less than the 50-point star.
    result = evaluate_trade(["star"], ["mid1", "mid2"], VALUES, depth_decay=0.5)

    assert result.verdict == "a"
    assert result.margin == pytest.approx(5.0)


def test_small_gaps_are_called_even() -> None:
    result = evaluate_trade(["mid1"], ["near_mid"], VALUES)  # 30 vs 29: a 3% gap

    assert result.verdict == "even"


def test_the_discount_applies_in_value_order_not_input_order() -> None:
    # The star always counts in full and the bench piece is discounted, however they're listed.
    expected = 50 + 10 * 0.85

    assert side_value(["bench", "star"], VALUES).adjusted_total == pytest.approx(expected)
    assert side_value(["star", "bench"], VALUES).adjusted_total == pytest.approx(expected)


def test_receiving_nothing_is_worth_zero() -> None:
    result = evaluate_trade(["star"], [], VALUES)

    assert result.side_b.adjusted_total == 0.0
    assert (result.verdict, result.margin_share) == ("a", 1.0)


def test_an_empty_trade_is_even() -> None:
    result = evaluate_trade([], [], VALUES)

    assert (result.verdict, result.margin, result.margin_share) == ("even", 0.0, 0.0)


def test_unknown_players_are_rejected_not_valued_at_zero() -> None:
    with pytest.raises(UnknownPlayerError) as excinfo:
        evaluate_trade(["star", "typo1"], ["typo2"], VALUES)

    assert excinfo.value.player_ids == ["typo1", "typo2"]
