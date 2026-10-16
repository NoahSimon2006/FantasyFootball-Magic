"""Pull completed trades out of the leagues the crawler found (redraft ones by default).

For each league, the weeks not fetched yet are requested from Sleeper, one request per week
(`/league/<id>/transactions/<week>`). Completed trades are stored with Sleeper's payload in
`trades.raw`, plus one `trade_assets` row per player, pick or FAAB amount that changed hands
(from `normalize_trade`).

Progress is kept per league: `leagues.trades_fetched_through_week` is the last week whose
trades are all stored. Only weeks that are over count, so the week still being played is
fetched again by the next run (more trades can complete in it). Fetching a week again is safe:
trades are keyed on Sleeper's transaction id, and a trade's assets are only written when its
trade row is new, so nothing is ever stored twice.
"""

import logging
from collections.abc import Collection, Iterator, Sequence
from dataclasses import asdict, dataclass

from sqlalchemy import (
    ColumnElement,
    Integer,
    Select,
    String,
    all_,
    case,
    func,
    literal,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.db.models import League, Trade, TradeAsset
from app.ingest.crawl import MAX_FAILURES_IN_A_ROW, REDRAFT_LEAGUE_TYPE
from app.ingest.normalize import normalize_trade
from app.sleeper.client import SleeperClient, SleeperUnavailableError
from app.sleeper.models import SleeperTransaction

logger = logging.getLogger(__name__)

# A trade deadline above this means "no deadline" (Sleeper uses 99): the regular season ends
# by week 18, so no real deadline is later.
LAST_REGULAR_SEASON_WEEK = 18


@dataclass(frozen=True)
class TradeIngestStats:
    """What one `ingest_trades` run did."""

    leagues_processed: int  # leagues whose missing weeks were fetched and stored
    weeks_fetched: int  # league-weeks fetched for them (one request each)
    trades_inserted: int  # completed trades stored for the first time
    assets_inserted: int  # trade_assets rows written for those trades
    requests_used: int  # Sleeper requests made, retries included
    # Leagues of the run's season and league type still missing trades from a week that's
    # over. A league whose only missing week is the one in progress doesn't count: that week
    # is fetched again every run.
    leagues_remaining: int


def ingest_trades(
    session: Session,
    client: SleeperClient,
    *,
    season: int,
    through_week: int,
    completed_through_week: int,
    max_requests: int,
    batch_size: int = 25,
    league_type: int = REDRAFT_LEAGUE_TYPE,
) -> TradeIngestStats:
    """Fetch and store the completed trades of `season`'s leagues up to `through_week`.

    `through_week` is how far to fetch (usually the current NFL week, possibly still being
    played); `completed_through_week` is the last week that's over. A league's progress is only
    recorded up to the completed week, so the next run fetches the in-progress week again. No
    league is fetched past its trade deadline, since no trades happen after it.

    Only leagues of `league_type` (Sleeper's settings.type) are touched. The value model uses
    redraft trades only, the default; other types exist so the stats report can check that
    type 0 really behaves like redraft (dynasty trades often include future picks, redraft
    trades rarely do).

    Leagues are taken least recently fetched first (never-fetched ones before all others).
    Each is fetched in full, stored and committed on its own, so a crash loses at most the
    league in flight; and a league is only started when the budget covers all of its missing
    weeks, so none is ever left half done. A league Sleeper fails on (`SleeperUnavailableError`,
    after the client's own retries) is logged and left for the next run; after
    `MAX_FAILURES_IN_A_ROW` failures in a row the run stops early.

    Raises:
        ValueError: if `batch_size` is below 1.
    """
    if batch_size < 1:
        raise ValueError(f"batch_size must be at least 1, got {batch_size}")
    requests_at_start = client.requests_made  # counts every attempt, retries included
    last_week = _last_relevant_week(through_week)
    failures_in_a_row = 0
    leagues_processed = weeks_fetched = trades_inserted = assets_inserted = 0

    for league_id, fetched_through, last in _claim_due_leagues(
        session,
        season=season,
        league_type=league_type,
        last_week=last_week,
        batch_size=batch_size,
    ):
        weeks = range(fetched_through + 1, last + 1)
        if client.requests_made - requests_at_start + len(weeks) > max_requests:
            break  # the budget can't cover this whole league, so don't start it
        try:
            # Every week is fetched before anything is written, so a failure partway through
            # leaves the league untouched rather than half done.
            transactions = [tx for week in weeks for tx in client.get_transactions(league_id, week)]
        except SleeperUnavailableError as exc:
            failures_in_a_row += 1
            logger.warning(
                "Sleeper unavailable for league %s; leaving it for the next run: %s",
                league_id,
                exc,
            )
            if failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                logger.error(
                    "Sleeper failed %d times in a row, so it's likely down or throttling us; "
                    "stopping this trade ingest early (finished leagues are saved)",
                    failures_in_a_row,
                )
                break
            continue
        failures_in_a_row = 0
        new_trades, new_assets = _store_trades(session, league_id, season, transactions)
        session.execute(
            update(League)
            .where(League.league_id == league_id)
            .values(
                # The in-progress week isn't recorded, so the next run fetches it again.
                # max(): never move progress backwards, even if this run was told that fewer
                # weeks are over than an earlier run was.
                trades_fetched_through_week=max(fetched_through, min(last, completed_through_week)),
                trades_fetched_at=func.now(),
            )
        )
        session.commit()
        leagues_processed += 1
        weeks_fetched += len(weeks)
        trades_inserted += new_trades
        assets_inserted += new_assets

    session.commit()  # releases the locks on leagues that were claimed but not finished
    leagues_remaining = session.execute(
        select(func.count())
        .select_from(League)
        .where(
            League.season == season,
            League.league_type == league_type,
            League.trades_fetched_through_week < func.least(last_week, completed_through_week),
        )
    ).scalar_one()
    return TradeIngestStats(
        leagues_processed=leagues_processed,
        weeks_fetched=weeks_fetched,
        trades_inserted=trades_inserted,
        assets_inserted=assets_inserted,
        requests_used=client.requests_made - requests_at_start,
        leagues_remaining=leagues_remaining,
    )


def _last_relevant_week(through_week: int) -> ColumnElement[int]:
    """SQL for a league's last week worth fetching: `through_week`, or the league's trade
    deadline if that comes first. Only deadlines in 1-18 are real (99 means "no deadline")."""
    return case(
        (
            League.trade_deadline.between(1, LAST_REGULAR_SEASON_WEEK),
            func.least(League.trade_deadline, through_week, type_=Integer),
        ),
        else_=through_week,
    )


def _claim_due_leagues(
    session: Session,
    *,
    season: int,
    league_type: int,
    last_week: ColumnElement[int],
    batch_size: int,
) -> Iterator[tuple[str, int, int]]:
    """Hand out due leagues one at a time, each row-locked: (league_id, fetched through, last
    relevant week). Due means a league of `season` and `league_type` with weeks to fetch.

    Leagues are claimed `batch_size` at a time with FOR UPDATE SKIP LOCKED, so a second
    ingest process passes over them. But the caller commits after every league, and a commit
    releases every lock the transaction holds, so each league is locked again (same query,
    narrowed to its id) right before it's handed out. If another process claimed or finished
    it in the meantime, it's skipped.

    Each league is handed out at most once per run. Without that, a league whose current week
    is still in progress (it stays due after being stored) or one Sleeper failed on would be
    claimed again and again until the budget ran out.
    """
    handed_out: set[str] = set()

    def due(*conditions: ColumnElement[bool]) -> Select[str, int, int]:
        return (
            select(
                League.league_id, League.trades_fetched_through_week, last_week.label("last_week")
            )
            .where(
                League.season == season,
                League.league_type == league_type,
                League.trades_fetched_through_week < last_week,
                *conditions,
            )
            .order_by(League.trades_fetched_at.asc().nulls_first(), League.league_id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )

    while batch := session.execute(due(_none_of(League.league_id, handed_out))).all():
        for league_id, _, _ in batch:
            # No handed-out filter needed here: every id in a batch is new to this run.
            league = session.execute(due(League.league_id == league_id)).one_or_none()
            if league is not None:
                handed_out.add(league_id)
                yield league


def _none_of(column: InstrumentedAttribute[str], ids: Collection[str]) -> ColumnElement[bool]:
    """SQL `column <> ALL(:ids)`, with the ids sent as ONE array parameter.

    `column.not_in(ids)` binds one parameter per id, and Postgres rejects a statement with more
    than 65,535 parameters, which a long run (one id per league it handles) could reach.
    """
    return column != all_(literal(list(ids), ARRAY(String)))


def _store_trades(
    session: Session, league_id: str, season: int, transactions: Sequence[SleeperTransaction]
) -> tuple[int, int]:
    """Store the completed trades among `transactions`. Returns (trades, assets) inserted.

    `trade_assets` has no natural key to deduplicate on, so a trade's assets are written only
    when its `trades` row is new, and RETURNING says which rows those are. Fetching a week again
    therefore adds nothing for the trades already stored.
    """
    trades = {
        tx.transaction_id: tx
        for tx in transactions
        if tx.type == "trade" and tx.status == "complete"
    }
    if not trades:
        return 0, 0
    inserted = set(
        session.scalars(
            insert(Trade)
            .values(
                [
                    {
                        "transaction_id": tx.transaction_id,
                        "league_id": league_id,
                        "season": season,
                        "week": tx.leg,
                        "created_at": tx.created_at,
                        "roster_ids": tx.roster_ids,
                        "raw": tx.model_dump(mode="json"),
                    }
                    for tx in trades.values()
                ]
            )
            .on_conflict_do_nothing(index_elements=[Trade.transaction_id])
            .returning(Trade.transaction_id)
        )
    )
    assets = [
        {"transaction_id": tx.transaction_id, **asdict(row)}
        for tx in trades.values()
        if tx.transaction_id in inserted
        for row in normalize_trade(tx)
    ]
    if assets:
        session.execute(insert(TradeAsset), assets)
    return len(inserted), len(assets)
