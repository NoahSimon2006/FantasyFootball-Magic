"""Snowball crawler: grow a sample of public Sleeper leagues outward from a few seed users.

How it spreads: a user's leagues are fetched (`/user/<id>/leagues/nfl/<season>`); every
redraft league among them has its members fetched (`/league/<id>/users`), and members we
haven't met yet join the frontier of users still to visit. Their leagues are fetched in turn,
and so on, each step reaching people one league further from the seeds.

Why a run can stop anywhere and the next one resumes: all progress lives in the database,
never in memory. A user is waiting while `crawl_users.leagues_fetched_at` is NULL, a league
while `leagues.members_fetched_at` is NULL. Work is claimed in small batches with
`SELECT ... LIMIT n FOR UPDATE SKIP LOCKED`, so two crawler processes never take the same
rows, and each batch is committed as soon as it's done, so a spent budget, a crash or Ctrl+C
loses at most the batch in flight. The next run simply claims the rows that are still NULL.

Why it's polite: a run stops at `max_requests` Sleeper calls (retries included), on top of
the client's own per-minute rate limit, and it gives up early when Sleeper keeps failing
rather than hammering a server that's struggling.

Data minimization: only Sleeper ids and league settings are stored, never usernames, display
names, avatars or league names.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import CrawlUser, League
from app.sleeper.client import SleeperClient, SleeperUnavailableError
from app.sleeper.models import SleeperLeague

logger = logging.getLogger(__name__)

# Sleeper's settings.type for a redraft league (1 = keeper, 2 = dynasty). Redraft leagues are
# the population the value model learns from, so they're the only ones whose members we crawl.
REDRAFT_LEAGUE_TYPE = 0

# This many Sleeper failures in a row (each already retried by the client) means Sleeper is
# down or throttling us, so the run stops instead of spending its budget on errors.
MAX_FAILURES_IN_A_ROW = 3


@dataclass(frozen=True)
class SeedResult:
    """What `seed_users` did."""

    resolved: int  # usernames Sleeper knew; their user ids are in the frontier
    unknown: list[str]  # usernames Sleeper doesn't know, in the order given


@dataclass(frozen=True)
class CrawlStats:
    """What one `crawl_leagues` run did."""

    users_processed: int  # users whose leagues were fetched
    leagues_found: int  # distinct leagues those users are in, of every type
    leagues_new: int  # of those, leagues that weren't stored before
    leagues_expanded: int  # redraft leagues whose members were fetched
    users_discovered: int  # members met for the first time (new frontier entries)
    requests_used: int  # Sleeper requests made, retries included
    frontier_remaining: int  # users still waiting for their leagues to be fetched


def seed_users(session: Session, client: SleeperClient, usernames: Sequence[str]) -> SeedResult:
    """Put the users behind `usernames` into the crawl frontier.

    A username Sleeper doesn't know is reported in the result, not raised: a typo in one seed
    shouldn't stop the others. Only the user id is stored (data minimization), and a user who
    is already in `crawl_users` keeps their progress, so seeding twice is harmless.
    """
    user_ids: list[str] = []
    unknown: list[str] = []
    for username in usernames:
        user = client.get_user(username)
        if user is None:
            unknown.append(username)
        else:
            user_ids.append(user.user_id)
    _add_to_frontier(session, user_ids)
    session.commit()
    return SeedResult(resolved=len(user_ids), unknown=unknown)


def crawl_leagues(
    session: Session,
    client: SleeperClient,
    *,
    seasons: Sequence[int],
    max_requests: int,
    batch_size: int = 25,
) -> CrawlStats:
    """Crawl outward from the frontier until the request budget is spent or nothing is left.

    Each round first expands a batch of waiting redraft leagues (one request each, and it's
    what grows the frontier), then fetches a batch of waiting users' leagues (one request per
    season in `seasons`). Nothing is started without budget left to finish it, so every row
    ends a run either fully processed or untouched.

    Leagues of every type are stored, because the stats report uses keeper and dynasty
    leagues to check that type 0 really means redraft; only redraft leagues get expanded.

    A user or league that Sleeper fails on (`SleeperUnavailableError`, after the client's own
    retries) is logged, left unprocessed for the next run, and skipped for the rest of this
    one. After `MAX_FAILURES_IN_A_ROW` failures in a row the run stops early; every batch
    finished before that is already committed.

    Raises:
        ValueError: if `seasons` is empty (every user would be marked as crawled without a
            single league fetched) or `batch_size` is below 1.
    """
    if not seasons:
        raise ValueError("crawl_leagues needs at least one season")
    if batch_size < 1:
        raise ValueError(f"batch_size must be at least 1, got {batch_size}")
    run = _CrawlRun(session, client, list(seasons), max_requests, batch_size)
    while not run.stopped:
        tried = run.expand_leagues()
        if not run.stopped:
            tried += run.fetch_users()
        if tried == 0:  # both queues are empty, or the budget can't cover the next item
            break
    return run.stats()


class _CrawlRun:
    """The state of one `crawl_leagues` call: its budget, failure streak and tallies."""

    def __init__(
        self,
        session: Session,
        client: SleeperClient,
        seasons: list[int],
        max_requests: int,
        batch_size: int,
    ) -> None:
        self.session = session
        self.client = client
        self.seasons = seasons
        self.max_requests = max_requests
        self.batch_size = batch_size
        # The client counts every HTTP attempt, retries included; the budget is the change.
        self.requests_at_start = client.requests_made
        self.failures_in_a_row = 0
        # Rows Sleeper failed on in this run. They stay unprocessed for the next run, but this
        # run must not claim them again, or one bad row would be retried batch after batch.
        # Only failures go here (processed rows leave their queue by themselves), so these
        # sets stay small.
        self.failed_league_ids: set[str] = set()
        self.failed_user_ids: set[str] = set()
        self.users_processed = 0
        self.league_ids_found: set[str] = set()
        self.leagues_new = 0
        self.leagues_expanded = 0
        self.users_discovered = 0

    @property
    def requests_used(self) -> int:
        return self.client.requests_made - self.requests_at_start

    @property
    def stopped(self) -> bool:
        return self.failures_in_a_row >= MAX_FAILURES_IN_A_ROW

    def expand_leagues(self) -> int:
        """Fetch the members of one batch of waiting redraft leagues. Returns how many were
        tried (0 when none is waiting or the budget can't cover one more)."""
        league_ids = self.session.scalars(
            select(League.league_id)
            .where(
                League.members_fetched_at.is_(None),
                League.league_type == REDRAFT_LEAGUE_TYPE,
                League.league_id.not_in(self.failed_league_ids),
            )
            .order_by(League.discovered_at, League.league_id)
            .limit(self.batch_size)
            .with_for_update(skip_locked=True)
        ).all()
        return self._process(
            league_ids,
            kind="league",
            cost=1,
            failed_ids=self.failed_league_ids,
            handle=self._expand_league,
        )

    def fetch_users(self) -> int:
        """Fetch the leagues of one batch of waiting users. Returns how many were tried."""
        user_ids = self.session.scalars(
            select(CrawlUser.user_id)
            .where(
                CrawlUser.leagues_fetched_at.is_(None),
                CrawlUser.user_id.not_in(self.failed_user_ids),
            )
            .order_by(CrawlUser.discovered_at, CrawlUser.user_id)
            .limit(self.batch_size)
            .with_for_update(skip_locked=True)
        ).all()
        return self._process(
            user_ids,
            kind="user",
            cost=len(self.seasons),
            failed_ids=self.failed_user_ids,
            handle=self._fetch_user,
        )

    def stats(self) -> CrawlStats:
        frontier_remaining = self.session.execute(
            select(func.count())
            .select_from(CrawlUser)
            .where(CrawlUser.leagues_fetched_at.is_(None))
        ).scalar_one()
        return CrawlStats(
            users_processed=self.users_processed,
            leagues_found=len(self.league_ids_found),
            leagues_new=self.leagues_new,
            leagues_expanded=self.leagues_expanded,
            users_discovered=self.users_discovered,
            requests_used=self.requests_used,
            frontier_remaining=frontier_remaining,
        )

    def _process(
        self,
        ids: Sequence[str],
        *,
        kind: str,
        cost: int,
        failed_ids: set[str],
        handle: Callable[[str], None],
    ) -> int:
        """Run `handle` on each claimed id while the budget covers `cost` more requests, then
        commit the batch, which also releases the rows that were claimed but not reached."""
        tried = 0
        for item_id in ids:
            if self.stopped or self.requests_used + cost > self.max_requests:
                break
            tried += 1
            try:
                handle(item_id)
            except SleeperUnavailableError as exc:
                failed_ids.add(item_id)
                self.failures_in_a_row += 1
                logger.warning(
                    "Sleeper unavailable for %s %s; leaving it for the next run: %s",
                    kind,
                    item_id,
                    exc,
                )
                if self.stopped:
                    logger.error(
                        "Sleeper failed %d times in a row, so it's likely down or throttling "
                        "us; stopping this crawl early (finished work is saved)",
                        self.failures_in_a_row,
                    )
                continue
            self.failures_in_a_row = 0
        self.session.commit()
        return tried

    def _expand_league(self, league_id: str) -> None:
        members = self.client.get_league_users(league_id)
        self.users_discovered += _add_to_frontier(
            self.session, [member.user_id for member in members]
        )
        self.session.execute(
            update(League)
            .where(League.league_id == league_id)
            .values(members_fetched_at=func.now())
        )
        self.leagues_expanded += 1

    def _fetch_user(self, user_id: str) -> None:
        # Every season is fetched before anything is written, so a failure partway through
        # leaves this user untouched rather than half done.
        leagues = [
            league
            for season in self.seasons
            for league in self.client.get_user_leagues(user_id, season)
        ]
        self.league_ids_found.update(league.league_id for league in leagues)
        self.leagues_new += _upsert_leagues(self.session, leagues)
        self.session.execute(
            update(CrawlUser)
            .where(CrawlUser.user_id == user_id)
            .values(leagues_fetched_at=func.now())
        )
        self.users_processed += 1


def _add_to_frontier(session: Session, user_ids: Sequence[str]) -> int:
    """Insert the user ids `crawl_users` doesn't have yet. Returns how many were new.

    ON CONFLICT DO NOTHING leaves a known user exactly as they are, so meeting someone again
    (in another league, or as a seed) never resets how far their crawl got.
    """
    if not user_ids:
        return 0
    inserted = session.scalars(
        insert(CrawlUser)
        .values([{"user_id": user_id} for user_id in dict.fromkeys(user_ids)])
        .on_conflict_do_nothing(index_elements=[CrawlUser.user_id])
        .returning(CrawlUser.user_id)
    ).all()
    return len(inserted)


def _upsert_leagues(session: Session, leagues: Sequence[SleeperLeague]) -> int:
    """Insert leagues not stored yet and refresh known ones. Returns how many were new.

    A known league gets its status and settings-derived columns refreshed (it moves from
    pre_draft to in_season; a commissioner changes the scoring), but never the crawl-progress
    columns: they aren't in the update at all, so meeting a league again through another
    member can't make it be expanded twice or forget how far its trades were fetched.
    """
    rows = {league.league_id: _league_columns(league) for league in leagues}
    if not rows:
        return 0
    # Two steps rather than one ON CONFLICT DO UPDATE, because RETURNING after DO NOTHING
    # names exactly the rows that were inserted, which is what `leagues_new` counts.
    inserted = set(
        session.scalars(
            insert(League)
            .values(list(rows.values()))
            .on_conflict_do_nothing(index_elements=[League.league_id])
            .returning(League.league_id)
        )
    )
    known = [row for league_id, row in rows.items() if league_id not in inserted]
    if known:
        # ORM bulk UPDATE by primary key: one UPDATE per row, setting only the keys given.
        session.execute(update(League), known)
    return len(inserted)


def _league_columns(league: SleeperLeague) -> dict[str, object]:
    """The `leagues` columns that Sleeper's data decides (the progress columns are ours)."""
    return {
        "league_id": league.league_id,
        "season": league.season,
        "status": league.status,
        "league_type": league.league_type,
        "total_rosters": league.total_rosters,
        "ppr": league.ppr,
        "is_superflex": league.is_superflex,
        "trade_deadline": league.settings.trade_deadline,
        "previous_league_id": league.previous_league_id,
    }
