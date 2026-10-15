"""Turn one Sleeper trade into "who gave what to whom" rows.

Sleeper spreads a trade across three differently shaped fields: players as two maps (`adds`:
who received each player, `drops`: who gave it up), draft picks as a list of moves, and FAAB
as a list of payments. The value model wants one shape: every asset with the roster that
received it and the roster that gave it up. That shape is `TradeAssetRow`.

Everything here is pure: no database, no network, no clock. The same transaction always
yields the same rows in the same order, so it's cheap to unit-test, and the rows can be
re-derived at any time from the raw payload kept in `trades.raw`.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.sleeper.models import SleeperTransaction

logger = logging.getLogger(__name__)

AssetType = Literal["player", "pick", "faab"]

# Players, then picks, then FAAB: the order a trade is usually read in (main pieces first).
_ASSET_TYPE_RANK: dict[AssetType, int] = {"player": 0, "pick": 1, "faab": 2}


@dataclass(frozen=True)
class TradeAssetRow:
    """One asset that changed hands in a trade.

    Field names match the `trade_assets` columns, minus `id` and `transaction_id` (the DB
    writer supplies those), so storing a row is
    `TradeAsset(transaction_id=tx.transaction_id, **asdict(row))`. Frozen because a row
    records something that already happened; nothing downstream should edit it.
    """

    asset_type: AssetType
    to_roster_id: int
    from_roster_id: int | None  # None only when Sleeper's payload doesn't name the giver
    player_id: str | None = None  # player rows; a team defense's id is its team code ("DEN")
    pick_season: int | None = None  # pick rows
    pick_round: int | None = None  # pick rows
    faab_amount: int | None = None  # faab rows: FAAB dollars


def normalize_trade(tx: SleeperTransaction) -> list[TradeAssetRow]:
    """Flatten a Sleeper trade into one row per asset, each with its receiver and giver.

    How each part of Sleeper's payload maps, and why:
    - Players come from `adds` (player -> receiving roster), with the giver looked up in
      `drops`. A player found only in `drops` was released (e.g. to make roster room), not
      sent to another roster, so it isn't an asset of the trade.
    - Picks: `owner_id` received the pick and `previous_owner_id` gave it up. The pick's
      original owner (`roster_id`) is not kept, because `trade_assets` has no column for it.
    - FAAB: `sender` gave `amount` dollars to `receiver`. A $0 move transfers nothing, and an
      extra row would make that side look like it got one more piece, which would skew the
      value model's adjustment for uneven (e.g. 2-for-1) trades.

    Rows are sorted by (receiver, players then picks then FAAB, player id, pick season, pick
    round, giver, FAAB amount). Receiver first keeps each side of the trade together, in
    roster order; the remaining fields break every tie on content. So the output depends
    only on what was traded, never on the order of Sleeper's JSON keys or lists, which keeps
    tests exact and re-deriving a trade's rows reproducible.

    `status` is not checked: which trades to keep (e.g. only completed ones) is the caller's
    decision.

    Raises:
        ValueError: if `tx` isn't a trade. Waivers and free-agent pickups aren't exchanges
            between rosters, and a caller that forgot to filter them out should fail loudly
            rather than feed them to the trade-value model.
    """
    if tx.type != "trade":
        raise ValueError(
            f"normalize_trade expects a trade, got type {tx.type!r} "
            f"(transaction {tx.transaction_id})"
        )

    rows: list[TradeAssetRow] = []

    drops = tx.drops or {}
    for player_id, to_roster_id in (tx.adds or {}).items():
        from_roster_id = drops.get(player_id)
        if from_roster_id is None:
            # Unexpected in a trade. Keep the row, because the receiver really did get the
            # player, but flag it so the payload gets looked at.
            logger.warning(
                "Trade %s: player %s is in adds but not in drops; recording an unknown giver",
                tx.transaction_id,
                player_id,
            )
        rows.append(
            TradeAssetRow(
                asset_type="player",
                to_roster_id=to_roster_id,
                from_roster_id=from_roster_id,
                player_id=player_id,
            )
        )

    for pick in tx.draft_picks or []:
        rows.append(
            TradeAssetRow(
                asset_type="pick",
                to_roster_id=pick.owner_id,
                from_roster_id=pick.previous_owner_id,
                pick_season=pick.season,
                pick_round=pick.round,
            )
        )

    for move in tx.waiver_budget or []:
        if move.amount == 0:
            continue  # moves no money; see the FAAB note above
        rows.append(
            TradeAssetRow(
                asset_type="faab",
                to_roster_id=move.receiver,
                from_roster_id=move.sender,
                faab_amount=move.amount,
            )
        )

    return sorted(rows, key=_sort_key)


def received_by_roster(rows: Sequence[TradeAssetRow]) -> dict[int, list[TradeAssetRow]]:
    """Group a trade's rows into its sides: roster id -> every asset that roster received.

    The value model compares a trade side by side (what each roster received), so this is
    the split it consumes. Grouping by receiver rather than giver keeps 3+ team trades
    simple: each roster is one side, even when its assets came from several teams.

    Rows keep their input order within a side, and sides appear in order of their first row,
    so `normalize_trade`'s output gives sides in roster-id order. A roster that received
    nothing has no key at all; use the trade's `roster_ids` to list every participant.
    """
    sides: dict[int, list[TradeAssetRow]] = {}
    for row in rows:
        sides.setdefault(row.to_roster_id, []).append(row)
    return sides


def _sort_key(row: TradeAssetRow) -> tuple[int, int, str, int, int, int, int]:
    """The row order documented on `normalize_trade`."""
    # Python can't compare None with an int or str, so None becomes a sentinel. A field the
    # row's asset type doesn't use is None on every row of that type, so its sentinel never
    # decides an order; the one meaningful None, an unknown giver, sorts first as -1.
    return (
        row.to_roster_id,
        _ASSET_TYPE_RANK[row.asset_type],
        row.player_id or "",
        row.pick_season or 0,
        row.pick_round or 0,
        -1 if row.from_roster_id is None else row.from_roster_id,
        row.faab_amount or 0,
    )
