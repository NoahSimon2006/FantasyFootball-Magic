"""Trade ingest: what's stored, which weeks are fetched, idempotency, budget and failures.

Sleeper is faked by `FakeSleeper` (no network, no real waiting). The database is the real
test Postgres, and everything a test writes is rolled back afterwards. The two real fixture
weeks: week 1 holds only waivers and free-agent moves, week 2 also three completed trades.
"""

import logging
from collections import Counter
from collections.abc import Iterator
from dataclasses import astuple
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import League, Trade, TradeAsset
from app.ingest.normalize import normalize_trade
from app.ingest.trades import TradeIngestStats, ingest_trades
from app.sleeper.client import SleeperClient, SleeperParseError
from app.sleeper.models import SleeperTransaction
from tests.ingest.fake_sleeper_crawl import (
    TEMPLATE_TRADE_ID,
    FakeSleeper,
    make_client,
    make_trade,
    recorded_sql,
)
from tests.sleeper.helpers import load_fixture

SEASON = 2026
LEAGUE_ID = "league-1"


@pytest.fixture
def fake() -> FakeSleeper:
    return FakeSleeper()


@pytest.fixture
def client(fake: FakeSleeper) -> Iterator[SleeperClient]:
    with make_client(fake) as client:
        yield client


def ingest(
    session: Session,
    client: SleeperClient,
    *,
    through_week: int = 2,
    completed_through_week: int | None = None,
    max_requests: int = 100,
    batch_size: int = 25,
) -> TradeIngestStats:
    """Ingest SEASON; every week through `through_week` is over unless told otherwise."""
    return ingest_trades(
        session,
        client,
        season=SEASON,
        through_week=through_week,
        completed_through_week=(
            through_week if completed_through_week is None else completed_through_week
        ),
        max_requests=max_requests,
        batch_size=batch_size,
    )


def add_league(
    session: Session,
    league_id: str = LEAGUE_ID,
    *,
    season: int = SEASON,
    league_type: int | None = 0,
    trade_deadline: int | None = 11,
    fetched_through: int = 0,
    fetched_at: datetime | None = None,
) -> None:
    """A league as the crawler stored it: a 12-team full-PPR redraft league by default."""
    session.add(
        League(
            league_id=league_id,
            season=season,
            status="in_season",
            league_type=league_type,
            total_rosters=12,
            ppr=1.0,
            is_superflex=False,
            trade_deadline=trade_deadline,
            trades_fetched_through_week=fetched_through,
            trades_fetched_at=fetched_at,
        )
    )
    session.flush()


def serve_fixture_weeks(fake: FakeSleeper, league_id: str = LEAGUE_ID) -> None:
    fake.add_week(league_id, 1, load_fixture("transactions_no_trade.json"))
    fake.add_week(league_id, 2, load_fixture("transactions_trade.json"))


def fixture_trades() -> list[SleeperTransaction]:
    """The completed trades of the week-2 fixture, parsed."""
    return [
        SleeperTransaction.model_validate(tx)
        for tx in load_fixture("transactions_trade.json")
        if tx["type"] == "trade" and tx["status"] == "complete"
    ]


def stored_trade_ids(session: Session) -> set[str]:
    return set(session.scalars(select(Trade.transaction_id)))


def count_rows(session: Session, model: type[Base]) -> int:
    return session.execute(select(func.count()).select_from(model)).scalar_one()


def fetched_through(session: Session, league_id: str = LEAGUE_ID) -> int:
    statement = select(League.trades_fetched_through_week).where(League.league_id == league_id)
    return session.scalars(statement).one()


def requested_weeks(fake: FakeSleeper, league_id: str = LEAGUE_ID) -> list[int]:
    prefix = f"/league/{league_id}/transactions/"
    return [int(path.removeprefix(prefix)) for path in fake.requests if path.startswith(prefix)]


def requested_leagues(fake: FakeSleeper) -> list[str]:
    """The league of each request, in order."""
    return [path.split("/")[2] for path in fake.requests]


# --- What gets stored -------------------------------------------------------------------------


def test_completed_trades_of_the_fetched_weeks_are_stored(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session)
    serve_fixture_weeks(fake)

    ingest(db_session, client)

    assert stored_trade_ids(db_session) == {tx.transaction_id for tx in fixture_trades()}


def test_each_new_trade_gets_one_asset_row_per_asset_that_moved(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session)
    serve_fixture_weeks(fake)

    ingest(db_session, client)

    stored = db_session.execute(
        select(
            TradeAsset.transaction_id,
            TradeAsset.asset_type,
            TradeAsset.to_roster_id,
            TradeAsset.from_roster_id,
            TradeAsset.player_id,
            TradeAsset.pick_season,
            TradeAsset.pick_round,
            TradeAsset.faab_amount,
        )
    ).all()
    expected = [
        (tx.transaction_id, *astuple(row)) for tx in fixture_trades() for row in normalize_trade(tx)
    ]
    # A Counter, not a set, so an asset stored twice would show up.
    assert Counter(tuple(row) for row in stored) == Counter(expected)


def test_stored_trade_keeps_its_league_week_and_sleeper_payload(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session)
    serve_fixture_weeks(fake)

    ingest(db_session, client)

    [tx] = [tx for tx in fixture_trades() if tx.transaction_id == TEMPLATE_TRADE_ID]
    trade = db_session.get_one(Trade, TEMPLATE_TRADE_ID)
    assert (
        trade.league_id,
        trade.season,
        trade.week,
        trade.created_at,
        trade.roster_ids,
        trade.raw,
    ) == (LEAGUE_ID, SEASON, 2, tx.created_at, [2, 9], tx.model_dump(mode="json"))


def test_waivers_free_agent_moves_and_incomplete_trades_are_ignored(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session)
    fake.add_week(
        LEAGUE_ID,
        1,
        [
            *load_fixture("transactions_no_trade.json"),
            make_trade("failed-trade", week=1, status="failed"),
            make_trade("completed-trade", week=1),
        ],
    )

    ingest(db_session, client, through_week=1)

    assert stored_trade_ids(db_session) == {"completed-trade"}


# --- Idempotency and the week in progress -------------------------------------------------------


def test_fetching_the_same_weeks_again_inserts_nothing_new(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session)
    serve_fixture_weeks(fake)
    ingest(db_session, client)
    rows_before = (count_rows(db_session, Trade), count_rows(db_session, TradeAsset))
    # Forget the league's progress, so the next run fetches weeks 1 and 2 all over again.
    db_session.execute(update(League).values(trades_fetched_through_week=0))

    stats = ingest(db_session, client)

    assert (stats.weeks_fetched, stats.trades_inserted, stats.assets_inserted) == (2, 0, 0)
    assert (count_rows(db_session, Trade), count_rows(db_session, TradeAsset)) == rows_before


def test_in_progress_week_is_fetched_again_next_run_without_duplicates(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session)
    fake.add_week(LEAGUE_ID, 3, [make_trade("early-trade", week=3)])
    ingest(db_session, client, through_week=3, completed_through_week=2)  # week 3 is still on
    fake.add_week(
        LEAGUE_ID, 3, [make_trade("early-trade", week=3), make_trade("late-trade", week=3)]
    )
    requests_before = len(fake.requests)

    ingest(db_session, client, through_week=3, completed_through_week=2)

    assets_per_trade = Counter(db_session.scalars(select(TradeAsset.transaction_id)))
    assert fake.requests[requests_before:] == [f"/league/{LEAGUE_ID}/transactions/3"]
    assert assets_per_trade == {"early-trade": 4, "late-trade": 4}


def test_league_waiting_only_on_the_week_in_progress_is_not_remaining(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session)

    stats = ingest(db_session, client, through_week=3, completed_through_week=2)

    assert stats.leagues_remaining == 0


# --- Which leagues and weeks are fetched --------------------------------------------------------


@pytest.mark.parametrize(
    ("trade_deadline", "last_week_fetched"),
    [(3, 3), (8, 6), (99, 6), (None, 6), (0, 6)],
    ids=[
        "deadline-before-through-week",
        "deadline-after-through-week",
        "99-means-no-deadline",
        "no-deadline-setting",
        "zero-is-not-a-deadline",
    ],
)
def test_weeks_are_fetched_through_the_trade_deadline_if_it_comes_first(
    db_session: Session,
    fake: FakeSleeper,
    client: SleeperClient,
    trade_deadline: int | None,
    last_week_fetched: int,
) -> None:
    add_league(db_session, trade_deadline=trade_deadline)

    ingest(db_session, client, through_week=6)

    assert requested_weeks(fake) == list(range(1, last_week_fetched + 1))


def test_league_past_its_trade_deadline_is_not_fetched_again(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session, trade_deadline=3)
    ingest(db_session, client, through_week=6)

    stats = ingest(db_session, client, through_week=7)

    assert stats.requests_used == 0


def test_only_redraft_leagues_of_the_requested_season_are_fetched(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session, "redraft-2026")
    add_league(db_session, "keeper-2026", league_type=1)
    add_league(db_session, "dynasty-2026", league_type=2)
    add_league(db_session, "no-type-2026", league_type=None)
    add_league(db_session, "redraft-2025", season=2025)

    ingest(db_session, client, through_week=1)  # no league_type given: redraft is the default

    assert set(requested_leagues(fake)) == {"redraft-2026"}


def test_a_run_for_another_league_type_touches_only_leagues_of_that_type(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session, "redraft-2026")
    add_league(db_session, "keeper-2026", league_type=1)
    add_league(db_session, "dynasty-2026", league_type=2)
    add_league(db_session, "dynasty-2025", season=2025, league_type=2)

    stats = ingest_trades(
        db_session,
        client,
        season=SEASON,
        through_week=1,
        completed_through_week=1,
        max_requests=100,
        league_type=2,
    )

    # Only the dynasty league is fetched, and the redraft league, though still due, isn't
    # counted as remaining by a dynasty run.
    assert (set(requested_leagues(fake)), stats.leagues_remaining) == ({"dynasty-2026"}, 0)


def test_leagues_fetched_longest_ago_go_first(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    # In id order "fetched-oct-14" would come first, so this only passes if age decides.
    oct_14 = datetime(2026, 10, 14, tzinfo=UTC)
    add_league(db_session, "fetched-oct-14", fetched_through=1, fetched_at=oct_14)
    add_league(
        db_session, "fetched-oct-7", fetched_through=1, fetched_at=datetime(2026, 10, 7, tzinfo=UTC)
    )
    add_league(db_session, "never-fetched")

    # never-fetched needs weeks 1 and 2, the others week 2 only: 3 requests cover two leagues.
    ingest(db_session, client, through_week=2, max_requests=3)

    assert requested_leagues(fake) == ["never-fetched", "never-fetched", "fetched-oct-7"]


# --- Budget, commits and failures ----------------------------------------------------------------


def test_ingest_stays_within_its_request_budget(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    for league_id in ("league-1", "league-2", "league-3"):
        add_league(db_session, league_id)

    # Each league needs weeks 1 and 2, a request each: a budget of 5 covers two leagues.
    stats = ingest(db_session, client, through_week=2, max_requests=5)

    assert (stats.requests_used, len(fake.requests)) == (4, 4)


def test_league_the_budget_cannot_cover_is_left_untouched(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    for league_id in ("league-1", "league-2", "league-3"):
        add_league(db_session, league_id)

    ingest(db_session, client, through_week=2, max_requests=5)

    assert (requested_weeks(fake, "league-3"), fetched_through(db_session, "league-3")) == ([], 0)


def test_ingest_stats_count_what_the_run_did(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session, "league-1")
    add_league(db_session, "league-2")
    serve_fixture_weeks(fake, "league-1")

    # Budget for league-1's two weeks, but not for league-2's as well.
    stats = ingest(db_session, client, through_week=2, max_requests=3)

    assert stats == TradeIngestStats(
        leagues_processed=1,
        weeks_fetched=2,
        trades_inserted=3,
        assets_inserted=11,
        requests_used=2,
        leagues_remaining=1,
    )


def test_a_crash_keeps_the_leagues_finished_before_it(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session, "league-1")
    add_league(db_session, "league-2")
    # A response that can't be parsed raises an error the ingest doesn't handle.
    fake.routes["/league/league-2/transactions/1"] = {"error": "not a list"}

    with pytest.raises(SleeperParseError):
        ingest(db_session, client, through_week=1)
    db_session.rollback()  # what the caller's session_scope does when the ingest raises

    assert (fetched_through(db_session, "league-1"), fetched_through(db_session, "league-2")) == (
        1,
        0,
    )


def test_unavailable_league_is_left_for_the_next_run_while_others_proceed(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session, "league-1")
    add_league(db_session, "league-2")
    # Week 1 of league-1 works and week 2 fails: the league must not be stored half done.
    fake.fail("/league/league-1/transactions/2")

    ingest(db_session, client, through_week=2)

    assert (fetched_through(db_session, "league-1"), fetched_through(db_session, "league-2")) == (
        0,
        2,
    )


def test_failed_league_is_not_retried_within_the_same_run(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session, "league-1")
    add_league(db_session, "league-2")
    fake.fail("/league/league-1/transactions/1")

    # Batches of one: each later batch would claim league-1 again if the run didn't skip it.
    ingest(db_session, client, through_week=1, batch_size=1)

    assert requested_leagues(fake).count("league-1") == 1


def test_unavailable_league_is_logged_with_its_id(
    db_session: Session,
    fake: FakeSleeper,
    client: SleeperClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    add_league(db_session)
    fake.fail(f"/league/{LEAGUE_ID}/transactions/1")

    with caplog.at_level(logging.WARNING, logger="app.ingest.trades"):
        ingest(db_session, client, through_week=1)

    [record] = [record for record in caplog.records if record.name == "app.ingest.trades"]
    assert (record.levelno, LEAGUE_ID in record.getMessage()) == (logging.WARNING, True)


def test_three_failures_in_a_row_stop_the_ingest(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    for number in range(1, 5):
        add_league(db_session, f"league-{number}")
    for number in range(1, 4):
        fake.fail(f"/league/league-{number}/transactions/1")

    ingest(db_session, client, through_week=1)

    assert "league-4" not in requested_leagues(fake)


# --- Guards ---------------------------------------------------------------------------------------


def test_ingest_claims_bounded_batches_and_skips_leagues_another_run_holds(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_league(db_session, "league-1")
    add_league(db_session, "league-2")

    with recorded_sql(db_session) as statements:
        ingest(db_session, client, through_week=1)

    claims = [sql for sql in statements if "FOR UPDATE" in sql]
    assert any("FROM leagues" in sql for sql in claims)
    assert all("LIMIT" in sql and "SKIP LOCKED" in sql for sql in claims)
