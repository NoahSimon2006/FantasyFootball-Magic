"""Tests for turning Sleeper trades into "who gave what to whom" rows.

Trades are built by `make_trade` in Sleeper's JSON shape and parsed through the real
`SleeperTransaction` model, so the tests also cover the parsing the ingest job relies on
(e.g. pick seasons arrive as strings).
"""

import logging
from dataclasses import fields

import pytest

from app.db.models import TradeAsset
from app.ingest.normalize import TradeAssetRow, normalize_trade, received_by_roster
from app.sleeper.models import SleeperTransaction


def make_trade(**overrides: object) -> SleeperTransaction:
    """A completed two-team trade as Sleeper sends it: roster 1 gives player "4046" to
    roster 2 for player "6794". Keyword arguments replace top-level fields."""
    # Pydantic ignores unknown keys, so a misspelled override would silently do nothing and
    # a test could pass without testing anything.
    unknown = overrides.keys() - SleeperTransaction.model_fields.keys()
    if unknown:
        raise TypeError(f"make_trade() got unknown SleeperTransaction fields: {sorted(unknown)}")
    payload: dict[str, object] = {
        "transaction_id": "1180000000000000001",
        "type": "trade",
        "status": "complete",
        "leg": 6,
        "created": 1_760_000_000_000,
        "roster_ids": [1, 2],
        "adds": {"4046": 2, "6794": 1},
        "drops": {"4046": 1, "6794": 2},
        "draft_picks": [],
        "waiver_budget": [],
    }
    return SleeperTransaction.model_validate(payload | overrides)


def sleeper_pick(
    season: str, pick_round: int, *, original_owner: int, giver: int, receiver: int
) -> dict[str, object]:
    """One `draft_picks` entry. Sleeper sends the season as a string."""
    return {
        "season": season,
        "round": pick_round,
        "roster_id": original_owner,
        "previous_owner_id": giver,
        "owner_id": receiver,
    }


def sleeper_faab(amount: int, *, sender: int, receiver: int) -> dict[str, object]:
    """One `waiver_budget` entry."""
    return {"sender": sender, "receiver": receiver, "amount": amount}


def player_row(player_id: str, *, giver: int | None, receiver: int) -> TradeAssetRow:
    return TradeAssetRow(
        asset_type="player", to_roster_id=receiver, from_roster_id=giver, player_id=player_id
    )


def pick_row(season: int, pick_round: int, *, giver: int, receiver: int) -> TradeAssetRow:
    return TradeAssetRow(
        asset_type="pick",
        to_roster_id=receiver,
        from_roster_id=giver,
        pick_season=season,
        pick_round=pick_round,
    )


def faab_row(amount: int, *, giver: int, receiver: int) -> TradeAssetRow:
    return TradeAssetRow(
        asset_type="faab", to_roster_id=receiver, from_roster_id=giver, faab_amount=amount
    )


def two_for_one_trade() -> SleeperTransaction:
    """Roster 1 gives "4046" and "4034" to roster 2 for "6794"."""
    return make_trade(
        adds={"4046": 2, "4034": 2, "6794": 1},
        drops={"4046": 1, "4034": 1, "6794": 2},
    )


def three_team_trade() -> SleeperTransaction:
    """1 sends "4046" to 2; 2 sends "6794" to 3; 3 sends "4866" to 1 and its defense to 2."""
    return make_trade(
        roster_ids=[1, 2, 3],
        adds={"4046": 2, "6794": 3, "4866": 1, "DEN": 2},
        drops={"4046": 1, "6794": 2, "4866": 3, "DEN": 3},
    )


def trade_missing_a_drop() -> SleeperTransaction:
    """Roster 2 receives "4046", but `drops` doesn't say who gave it up."""
    return make_trade(
        transaction_id="tx-missing-drop", adds={"4046": 2, "6794": 1}, drops={"6794": 2}
    )


def test_one_for_one_trade_moves_each_player_from_giver_to_receiver() -> None:
    assert normalize_trade(make_trade()) == [
        player_row("6794", giver=2, receiver=1),
        player_row("4046", giver=1, receiver=2),
    ]


def test_two_for_one_trade_lists_both_players_the_receiver_got() -> None:
    assert normalize_trade(two_for_one_trade()) == [
        player_row("6794", giver=2, receiver=1),
        player_row("4034", giver=1, receiver=2),
        player_row("4046", giver=1, receiver=2),
    ]


def test_received_by_roster_splits_a_two_for_one_into_two_sides() -> None:
    sides = received_by_roster(normalize_trade(two_for_one_trade()))

    assert sides == {
        1: [player_row("6794", giver=2, receiver=1)],
        2: [player_row("4034", giver=1, receiver=2), player_row("4046", giver=1, receiver=2)],
    }


def test_draft_pick_moves_from_previous_owner_to_new_owner() -> None:
    # Roster 2 passes on a pick it had acquired from roster 7: the giver is 2, not 7.
    acquired_pick = sleeper_pick("2027", 2, original_owner=7, giver=2, receiver=1)
    trade = make_trade(draft_picks=[acquired_pick])

    assert normalize_trade(trade) == [
        player_row("6794", giver=2, receiver=1),
        pick_row(2027, 2, giver=2, receiver=1),
        player_row("4046", giver=1, receiver=2),
    ]


def test_faab_moves_from_sender_to_receiver() -> None:
    trade = make_trade(waiver_budget=[sleeper_faab(15, sender=2, receiver=1)])

    assert normalize_trade(trade) == [
        player_row("6794", giver=2, receiver=1),
        faab_row(15, giver=2, receiver=1),
        player_row("4046", giver=1, receiver=2),
    ]


def test_zero_dollar_faab_move_is_skipped() -> None:
    paid = sleeper_faab(15, sender=2, receiver=1)
    trade = make_trade(waiver_budget=[paid, sleeper_faab(0, sender=1, receiver=2)])

    assert normalize_trade(trade) == normalize_trade(make_trade(waiver_budget=[paid]))


def test_three_team_trade_records_each_asset_with_its_own_giver() -> None:
    assert normalize_trade(three_team_trade()) == [
        player_row("4866", giver=3, receiver=1),
        player_row("4046", giver=1, receiver=2),
        player_row("DEN", giver=3, receiver=2),
        player_row("6794", giver=2, receiver=3),
    ]


def test_received_by_roster_gives_a_three_team_trade_three_sides() -> None:
    sides = received_by_roster(normalize_trade(three_team_trade()))

    assert list(sides) == [1, 2, 3]


def test_picks_only_trade_with_no_adds_or_drops_yields_pick_rows() -> None:
    trade = make_trade(
        adds=None,
        drops=None,
        draft_picks=[
            sleeper_pick("2027", 5, original_owner=1, giver=1, receiver=2),
            sleeper_pick("2027", 3, original_owner=2, giver=2, receiver=1),
        ],
    )

    assert normalize_trade(trade) == [
        pick_row(2027, 3, giver=2, receiver=1),
        pick_row(2027, 5, giver=1, receiver=2),
    ]


def test_player_missing_from_drops_is_kept_with_an_unknown_giver() -> None:
    rows = normalize_trade(trade_missing_a_drop())

    assert player_row("4046", giver=None, receiver=2) in rows


def test_player_missing_from_drops_logs_a_warning_naming_the_trade_and_player(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.ingest.normalize"):
        normalize_trade(trade_missing_a_drop())

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "tx-missing-drop" in warnings[0] and "4046" in warnings[0]


def test_player_only_in_drops_is_not_an_asset() -> None:
    # Given up but received by nobody: released (e.g. to make roster room), not traded.
    trade = make_trade(drops={"4046": 1, "6794": 2, "4866": 1})

    assert normalize_trade(trade) == normalize_trade(make_trade())


@pytest.mark.parametrize("tx_type", ["waiver", "free_agent", "commissioner"])
def test_non_trade_transaction_raises_value_error(tx_type: str) -> None:
    with pytest.raises(ValueError, match=tx_type):
        normalize_trade(make_trade(type=tx_type))


def test_rows_sort_by_receiver_then_players_picks_faab() -> None:
    trade = make_trade(
        adds={"6794": 1, "DEN": 1, "4046": 2},
        drops={"6794": 2, "DEN": 2, "4046": 1},
        draft_picks=[
            sleeper_pick("2028", 1, original_owner=2, giver=2, receiver=1),
            sleeper_pick("2027", 4, original_owner=2, giver=2, receiver=1),
            sleeper_pick("2027", 2, original_owner=2, giver=2, receiver=1),
        ],
        waiver_budget=[sleeper_faab(20, sender=2, receiver=1)],
    )

    assert normalize_trade(trade) == [
        player_row("6794", giver=2, receiver=1),
        player_row("DEN", giver=2, receiver=1),
        pick_row(2027, 2, giver=2, receiver=1),
        pick_row(2027, 4, giver=2, receiver=1),
        pick_row(2028, 1, giver=2, receiver=1),
        faab_row(20, giver=2, receiver=1),
        player_row("4046", giver=1, receiver=2),
    ]


def test_row_order_ignores_the_order_of_sleepers_keys_and_lists() -> None:
    # For each tie-breaker (player id; pick season, round, giver; FAAB giver, amount) some
    # pair of rows differs in only that field, so leaving any of them out of the sort key
    # lets Sleeper's input order leak through and fails this test.
    adds = {"DEN": 1, "4046": 2, "6794": 1, "4866": 3}
    drops = {"DEN": 2, "4046": 1, "6794": 2, "4866": 2}
    picks = [
        sleeper_pick("2027", 2, original_owner=1, giver=1, receiver=2),
        sleeper_pick("2028", 2, original_owner=1, giver=1, receiver=2),
        sleeper_pick("2027", 3, original_owner=1, giver=1, receiver=2),
        sleeper_pick("2027", 2, original_owner=3, giver=3, receiver=2),
    ]
    faab = [
        sleeper_faab(10, sender=2, receiver=1),
        sleeper_faab(10, sender=3, receiver=1),
        sleeper_faab(5, sender=2, receiver=1),
    ]

    forward = make_trade(
        roster_ids=[1, 2, 3], adds=adds, drops=drops, draft_picks=picks, waiver_budget=faab
    )
    backward = make_trade(
        roster_ids=[3, 2, 1],
        adds=dict(reversed(adds.items())),
        drops=dict(reversed(drops.items())),
        draft_picks=picks[::-1],
        waiver_budget=faab[::-1],
    )

    assert normalize_trade(forward) == normalize_trade(backward)


def test_row_fields_match_the_trade_assets_columns() -> None:
    # The DB writer stores a row as TradeAsset(transaction_id=..., **asdict(row)), so the
    # dataclass and the table must not drift apart.
    columns = set(TradeAsset.__table__.columns.keys()) - {"id", "transaction_id"}

    assert {field.name for field in fields(TradeAssetRow)} == columns
