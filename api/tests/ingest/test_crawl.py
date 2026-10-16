"""The snowball crawler: seeding, spreading through redraft leagues, budget, resuming, failures.

Sleeper is faked by `FakeSleeper` (no network, no real waiting). The database is the real
test Postgres, and everything a test writes is rolled back afterwards.
"""

import logging
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CrawlUser, League
from app.ingest.crawl import CrawlStats, SeedResult, crawl_leagues, seed_users
from app.sleeper.client import SleeperClient, SleeperParseError
from tests.ingest.fake_sleeper_crawl import FakeSleeper, make_client, make_league, recorded_sql

SEASON = 2026
EARLIER_RUN = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)  # when some earlier run did its work


@pytest.fixture
def fake() -> FakeSleeper:
    return FakeSleeper()


@pytest.fixture
def client(fake: FakeSleeper) -> Iterator[SleeperClient]:
    with make_client(fake) as client:
        yield client


def crawl(
    session: Session, client: SleeperClient, *, max_requests: int = 100, batch_size: int = 25
) -> CrawlStats:
    """A crawl of SEASON only, so each user costs one request."""
    return crawl_leagues(
        session, client, seasons=[SEASON], max_requests=max_requests, batch_size=batch_size
    )


def add_to_frontier(session: Session, *user_ids: str) -> None:
    session.add_all(CrawlUser(user_id=user_id) for user_id in user_ids)
    session.flush()


def crawled_user_ids(session: Session) -> set[str]:
    """Users whose leagues have been fetched."""
    statement = select(CrawlUser.user_id).where(CrawlUser.leagues_fetched_at.is_not(None))
    return set(session.scalars(statement))


def waiting_user_ids(session: Session) -> set[str]:
    """Users still in the frontier."""
    statement = select(CrawlUser.user_id).where(CrawlUser.leagues_fetched_at.is_(None))
    return set(session.scalars(statement))


def requested_user_ids(fake: FakeSleeper) -> list[str]:
    """Whose leagues were requested, one entry per request, in order."""
    return [path.split("/")[2] for path in fake.requests if path.startswith("/user/")]


def seed_in_one_league_of_each_type(session: Session, fake: FakeSleeper) -> None:
    """`seed` plays in a redraft, a keeper and a dynasty league; the redraft league's other
    members are `mate-1` and `mate-2`. Only the redraft league has a members route, so trying
    to expand the others fails the test."""
    add_to_frontier(session, "seed")
    fake.add_leagues(
        "seed",
        SEASON,
        make_league("redraft", league_type=0),
        make_league("keeper", league_type=1),
        make_league("dynasty", league_type=2),
    )
    fake.add_members("redraft", "seed", "mate-1", "mate-2")


def rediscover_a_known_league(session: Session, fake: FakeSleeper) -> None:
    """An earlier run stored `redraft` while it was pre-draft (10 teams, half PPR), expanded it,
    and fetched its trades through week 5. Now `user-1` turns out to play in it too, and
    Sleeper shows the league in season with 12 full-PPR teams."""
    session.add(
        League(
            league_id="redraft",
            season=SEASON,
            status="pre_draft",
            league_type=0,
            total_rosters=10,
            ppr=0.5,
            is_superflex=False,
            trade_deadline=11,
            members_fetched_at=EARLIER_RUN,
            trades_fetched_through_week=5,
            trades_fetched_at=EARLIER_RUN,
        )
    )
    add_to_frontier(session, "user-1")
    fake.add_leagues("user-1", SEASON, make_league("redraft", status="in_season"))


def three_users_failing_in_a_row(session: Session, fake: FakeSleeper) -> None:
    """user-0 is fine, Sleeper fails on user-1 to user-3, and user-4 would be fine again."""
    add_to_frontier(session, "user-0", "user-1", "user-2", "user-3", "user-4")
    for user_id in ("user-1", "user-2", "user-3"):
        fake.fail(f"/user/{user_id}/leagues/nfl/{SEASON}")


# --- Seeding --------------------------------------------------------------------------------


def test_seed_users_resolves_known_usernames_and_reports_unknown_ones(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    fake.add_user("known_user", "seed")

    result = seed_users(db_session, client, ["known_user", "no_such_user_zz9"])

    assert result == SeedResult(resolved=1, unknown=["no_such_user_zz9"])


def test_seed_users_puts_the_user_id_into_the_frontier(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    fake.add_user("known_user", "seed")

    seed_users(db_session, client, ["known_user", "no_such_user_zz9"])

    assert waiting_user_ids(db_session) == {"seed"}


def test_seeding_an_already_crawled_user_keeps_their_progress(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    db_session.add(CrawlUser(user_id="seed", leagues_fetched_at=EARLIER_RUN))
    db_session.flush()
    fake.add_user("known_user", "seed")

    seed_users(db_session, client, ["known_user"])

    statement = select(CrawlUser.leagues_fetched_at).where(CrawlUser.user_id == "seed")
    assert db_session.scalars(statement).one() == EARLIER_RUN


# --- Spreading through leagues ---------------------------------------------------------------


def test_crawl_stores_the_leagues_of_every_type_it_finds(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    seed_in_one_league_of_each_type(db_session, fake)

    crawl(db_session, client)

    stored = db_session.execute(select(League.league_id, League.league_type)).all()
    assert dict(stored) == {"redraft": 0, "keeper": 1, "dynasty": 2}


def test_crawl_expands_redraft_leagues_only(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    seed_in_one_league_of_each_type(db_session, fake)

    crawl(db_session, client)

    expanded = db_session.scalars(
        select(League.league_id).where(League.members_fetched_at.is_not(None))
    ).all()
    member_requests = [path for path in fake.requests if path.endswith("/users")]
    assert (expanded, member_requests) == (["redraft"], ["/league/redraft/users"])


def test_members_of_a_redraft_league_join_the_frontier(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    seed_in_one_league_of_each_type(db_session, fake)

    # Budget for the seed's leagues and the redraft league's members, not for anyone after.
    crawl(db_session, client, max_requests=2)

    assert waiting_user_ids(db_session) == {"mate-1", "mate-2"}


def test_crawl_stats_count_what_the_run_did(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    seed_in_one_league_of_each_type(db_session, fake)
    fake.add_leagues("mate-1", SEASON, make_league("redraft"))  # found twice, counted once

    stats = crawl(db_session, client)

    # Requests: the seed's leagues, the redraft league's members, then each mate's leagues.
    assert stats == CrawlStats(
        users_processed=3,
        leagues_found=3,
        leagues_new=3,
        leagues_expanded=1,
        users_discovered=2,
        requests_used=4,
        frontier_remaining=0,
    )


def test_users_waiting_longest_are_crawled_first(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    # In id order "newer" would come first, so this only passes if discovery order wins.
    db_session.add_all(
        [
            CrawlUser(user_id="newer", discovered_at=datetime(2026, 10, 2, tzinfo=UTC)),
            CrawlUser(user_id="older", discovered_at=datetime(2026, 10, 1, tzinfo=UTC)),
        ]
    )
    db_session.flush()

    crawl(db_session, client, max_requests=1)

    assert crawled_user_ids(db_session) == {"older"}


# --- Budget and resuming ----------------------------------------------------------------------


def test_crawl_stays_within_its_request_budget(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_to_frontier(db_session, "user-1", "user-2", "user-3")

    # Two seasons, so each user costs two requests: a budget of 5 covers two users.
    stats = crawl_leagues(db_session, client, seasons=[2025, 2026], max_requests=5)

    assert (stats.requests_used, len(fake.requests)) == (4, 4)


def test_user_the_budget_cannot_cover_is_left_untouched(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_to_frontier(db_session, "user-1", "user-2", "user-3")

    crawl_leagues(db_session, client, seasons=[2025, 2026], max_requests=5)

    # Not half done: no season of user-3's was requested, and user-3 is still waiting.
    assert ("user-3" in requested_user_ids(fake), waiting_user_ids(db_session)) == (
        False,
        {"user-3"},
    )


def test_second_run_resumes_without_refetching_finished_work(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    seed_in_one_league_of_each_type(db_session, fake)
    crawl(db_session, client, max_requests=2)  # the seed's leagues, then the league's members
    first_run_requests = len(fake.requests)

    crawl(db_session, client)

    assert fake.requests[first_run_requests:] == [
        "/user/mate-1/leagues/nfl/2026",
        "/user/mate-2/leagues/nfl/2026",
    ]


def test_a_crash_keeps_the_batches_finished_before_it(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_to_frontier(db_session, "user-1", "user-2")
    # A response that can't be parsed raises an error the crawler doesn't handle.
    fake.routes[f"/user/user-2/leagues/nfl/{SEASON}"] = {"error": "not a list"}

    with pytest.raises(SleeperParseError):
        crawl(db_session, client, batch_size=1)
    db_session.rollback()  # what the caller's session_scope does when the crawl raises

    assert crawled_user_ids(db_session) == {"user-1"}


def test_rediscovered_league_keeps_its_crawl_progress(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    rediscover_a_known_league(db_session, fake)

    crawl(db_session, client)

    progress = db_session.execute(
        select(
            League.members_fetched_at,
            League.trades_fetched_through_week,
            League.trades_fetched_at,
        ).where(League.league_id == "redraft")
    ).one()
    assert tuple(progress) == (EARLIER_RUN, 5, EARLIER_RUN)


def test_rediscovered_league_gets_its_settings_refreshed(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    rediscover_a_known_league(db_session, fake)

    crawl(db_session, client)

    settings = db_session.execute(
        select(League.status, League.total_rosters, League.ppr).where(League.league_id == "redraft")
    ).one()
    assert tuple(settings) == ("in_season", 12, 1.0)


# --- When Sleeper fails -------------------------------------------------------------------------


def test_unavailable_user_is_left_for_the_next_run_while_others_proceed(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_to_frontier(db_session, "user-1", "user-2", "user-3")
    fake.fail(f"/user/user-2/leagues/nfl/{SEASON}")

    crawl(db_session, client)

    assert (crawled_user_ids(db_session), waiting_user_ids(db_session)) == (
        {"user-1", "user-3"},
        {"user-2"},
    )


def test_failed_user_is_not_retried_within_the_same_run(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_to_frontier(db_session, "user-1", "user-2", "user-3")
    fake.fail(f"/user/user-2/leagues/nfl/{SEASON}")

    # Batches of one: each later batch would claim user-2 again if the run didn't skip it.
    crawl(db_session, client, batch_size=1)

    assert requested_user_ids(fake).count("user-2") == 1


def test_failed_user_is_retried_by_the_next_run(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    add_to_frontier(db_session, "user-1")
    fake.fail(f"/user/user-1/leagues/nfl/{SEASON}")
    crawl(db_session, client)
    fake.failing.clear()  # Sleeper is back

    crawl(db_session, client)

    assert crawled_user_ids(db_session) == {"user-1"}


def test_unavailable_user_is_logged_with_its_id(
    db_session: Session,
    fake: FakeSleeper,
    client: SleeperClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    add_to_frontier(db_session, "user-1")
    fake.fail(f"/user/user-1/leagues/nfl/{SEASON}")

    with caplog.at_level(logging.WARNING, logger="app.ingest.crawl"):
        crawl(db_session, client)

    [record] = [record for record in caplog.records if record.name == "app.ingest.crawl"]
    assert (record.levelno, "user-1" in record.getMessage()) == (logging.WARNING, True)


def test_three_failures_in_a_row_stop_the_run(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    three_users_failing_in_a_row(db_session, fake)

    crawl(db_session, client)

    assert "user-4" not in requested_user_ids(fake)


def test_work_finished_before_an_early_stop_is_committed(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    three_users_failing_in_a_row(db_session, fake)
    crawl(db_session, client)

    db_session.rollback()  # throws away anything the crawl left uncommitted

    assert crawled_user_ids(db_session) == {"user-0"}


# --- Guards ---------------------------------------------------------------------------------------


def test_crawl_claims_bounded_batches_and_skips_rows_another_crawler_holds(
    db_session: Session, fake: FakeSleeper, client: SleeperClient
) -> None:
    seed_in_one_league_of_each_type(db_session, fake)

    with recorded_sql(db_session) as statements:
        crawl(db_session, client)

    claims = [sql for sql in statements if "FOR UPDATE" in sql]
    assert any("FROM crawl_users" in sql for sql in claims)
    assert any("FROM leagues" in sql for sql in claims)
    assert all("LIMIT" in sql and "SKIP LOCKED" in sql for sql in claims)


def test_crawl_refuses_an_empty_list_of_seasons(db_session: Session, client: SleeperClient) -> None:
    # Otherwise every waiting user would be marked crawled without a league being fetched.
    with pytest.raises(ValueError, match="season"):
        crawl_leagues(db_session, client, seasons=[], max_requests=10)
