"""Command-line entry point for the ingest jobs. Run from `api/`:

    uv run python -m app.ingest players
    uv run python -m app.ingest projections [--season S] [--from-week W] [--to-week W]
    uv run python -m app.ingest seed
    uv run python -m app.ingest crawl [--max-requests N] [--seasons S [S ...]]
    uv run python -m app.ingest trades [--season S] [--max-requests N]
    uv run python -m app.ingest stats

Each run opens one Sleeper client and one `session_scope()`: the command's writes are
committed when it finishes and rolled back if it fails (jobs may also commit as they go).
Log lines go to stderr; `stats` prints its report to stdout.
"""

import argparse
import logging
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import session_scope
from app.ingest.players import ingest_players
from app.ingest.projections import ingest_projections
from app.ingest.stats import collect_stats, format_stats
from app.sleeper.client import SleeperClient, SleeperError

# Named explicitly: under `python -m`, __name__ is "__main__", which says nothing in a log.
logger = logging.getLogger("app.ingest")

LAST_REGULAR_SEASON_WEEK = 18
DEFAULT_CRAWL_MAX_REQUESTS = 1500
DEFAULT_TRADES_MAX_REQUESTS = 3000

# A command gets the parsed arguments, the session, and the client, and returns a short
# summary of what it did.
Command = Callable[[argparse.Namespace, Session, SleeperClient], str]


class CommandError(Exception):
    """A failure worth one log line rather than a traceback, such as missing configuration."""


def main(argv: Sequence[str] | None = None) -> int:
    """Run one ingest command and return the process exit code (0 on success)."""
    args = build_parser().parse_args(argv)
    configure_logging()
    command: Command = args.run
    started = time.monotonic()
    with open_client() as client:
        try:
            with session_scope() as session:
                summary = command(args, session, client)
        except (SleeperError, CommandError) as exc:
            logger.error(
                "%s failed | %s | Sleeper requests: %d", args.command, exc, client.requests_made
            )
            return 1
    logger.info(
        "%s done | %s | Sleeper requests: %d | %.1fs",
        args.command,
        summary,
        client.requests_made,
        time.monotonic() - started,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.ingest", description="Pull Sleeper data into the database."
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    players = commands.add_parser("players", help="upsert NFL players at fantasy positions")
    players.set_defaults(run=_players)

    projections = commands.add_parser(
        "projections", help="snapshot weekly projections under today's date (UTC)"
    )
    projections.add_argument("--season", type=int, help="default: the current NFL season")
    projections.add_argument(
        "--from-week", type=int, help="default: this week in the current season, else week 1"
    )
    projections.add_argument(
        "--to-week",
        type=int,
        default=LAST_REGULAR_SEASON_WEEK,
        help="default: %(default)s, the last regular-season week",
    )
    projections.set_defaults(run=_projections)

    seed = commands.add_parser(
        "seed", help="start the crawl frontier from the SLEEPER_SEED_USERNAMES users"
    )
    seed.set_defaults(run=_seed)

    crawl = commands.add_parser("crawl", help="discover leagues, starting from the frontier")
    crawl.add_argument(
        "--max-requests",
        type=int,
        default=DEFAULT_CRAWL_MAX_REQUESTS,
        help="Sleeper request budget for this run (default: %(default)s)",
    )
    crawl.add_argument(
        "--seasons", type=int, nargs="+", help="default: the current and previous seasons"
    )
    crawl.set_defaults(run=_crawl)

    trades = commands.add_parser("trades", help="fetch trades from the crawled leagues")
    trades.add_argument("--season", type=int, help="default: the current NFL season")
    trades.add_argument(
        "--max-requests",
        type=int,
        default=DEFAULT_TRADES_MAX_REQUESTS,
        help="Sleeper request budget for this run (default: %(default)s)",
    )
    trades.add_argument(
        "--league-type",
        type=int,
        choices=(0, 1, 2),
        default=0,
        help=(
            "Sleeper settings.type of the leagues to fetch: 0 redraft (default, what values "
            "are learned from), 1 keeper, 2 dynasty. Use 2 with a small --max-requests to "
            "collect a sample for the stats report's league-type check."
        ),
    )
    trades.set_defaults(run=_trades)

    stats = commands.add_parser("stats", help="print row counts and the league-type check")
    stats.set_defaults(run=_stats)
    return parser


def configure_logging() -> None:
    """INFO and above to stderr, one timestamped line per message."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    # httpx2 logs every request at INFO, so a 1,500-request crawl would bury the summaries.
    logging.getLogger("httpx2").setLevel(logging.WARNING)


def open_client() -> SleeperClient:
    """The run's Sleeper client. Tests replace this to serve canned responses instead."""
    return SleeperClient.from_settings(get_settings())


def utc_now() -> datetime:
    """The current time in UTC. Tests replace this to pin the clock."""
    return datetime.now(UTC)


# --- Commands ------------------------------------------------------------------------------
# The crawl and trades jobs are imported inside their commands, so a problem in one job's
# module can't stop the other commands from running.


def _players(args: argparse.Namespace, session: Session, client: SleeperClient) -> str:
    written = ingest_players(session, client, now=utc_now())
    return f"players upserted: {written:,}"


def _projections(args: argparse.Namespace, session: Session, client: SleeperClient) -> str:
    season: int | None = args.season
    from_week: int | None = args.from_week
    if season is None or from_week is None:  # only then does Sleeper need to be asked
        state = client.get_nfl_state()
        if season is None:
            season = state.season
        if from_week is None:
            # The current season's earlier weeks are already played. max(): weeks start at
            # 1, so this guards against a week 0 if Sleeper reports one off-season.
            from_week = max(state.week, 1) if season == state.season else 1
    to_week: int = args.to_week
    if from_week > to_week:
        raise CommandError(f"no weeks to fetch: from week {from_week} is after week {to_week}")
    # A UTC calendar day, like every timestamp in the database, so a snapshot's label
    # doesn't depend on the time zone of the machine that ran the job.
    snapshot_date = utc_now().date()
    written = ingest_projections(
        session,
        client,
        season=season,
        weeks=range(from_week, to_week + 1),
        snapshot_date=snapshot_date,
    )
    return (
        f"projection rows stored: {written:,} ({season} weeks {from_week}-{to_week}, "
        f"snapshot {snapshot_date.isoformat()})"
    )


def _seed(args: argparse.Namespace, session: Session, client: SleeperClient) -> str:
    from app.ingest.crawl import seed_users

    usernames = get_settings().seed_usernames
    if not usernames:
        raise CommandError(
            "no seed usernames: set SLEEPER_SEED_USERNAMES (comma-separated) in api/.env "
            "or the environment"
        )
    result = seed_users(session, client, usernames)
    if result.unknown:
        logger.warning("No Sleeper user with these usernames: %s", ", ".join(result.unknown))
    if not result.resolved:
        raise CommandError("none of the seed usernames exist on Sleeper")
    return f"seed usernames resolved: {result.resolved} of {len(usernames)}"


def _crawl(args: argparse.Namespace, session: Session, client: SleeperClient) -> str:
    from app.ingest.crawl import crawl_leagues

    seasons: list[int]
    if args.seasons:
        seasons = args.seasons
    else:
        state = client.get_nfl_state()
        seasons = [state.season, state.previous_season]
    stats = crawl_leagues(session, client, seasons=seasons, max_requests=args.max_requests)
    return f"seasons {', '.join(map(str, seasons))}: {stats}"


def _trades(args: argparse.Namespace, session: Session, client: SleeperClient) -> str:
    from app.ingest.trades import ingest_trades

    state = client.get_nfl_state()
    season: int = state.season if args.season is None else args.season
    if season == state.season:
        # This week's trades may still be coming in: fetch through this week, but count
        # only the weeks before it as complete. max(): never week -1 if Sleeper says week 0.
        through_week, completed_through_week = state.week, max(state.week - 1, 0)
    else:
        # A past season is over, so every regular-season week is complete.
        through_week = completed_through_week = LAST_REGULAR_SEASON_WEEK
    stats = ingest_trades(
        session,
        client,
        season=season,
        through_week=through_week,
        completed_through_week=completed_through_week,
        max_requests=args.max_requests,
        league_type=args.league_type,
    )
    return f"season {season} league type {args.league_type} through week {through_week}: {stats}"


def _stats(args: argparse.Namespace, session: Session, client: SleeperClient) -> str:
    print(format_stats(collect_stats(session)))
    return "report printed"


if __name__ == "__main__":
    sys.exit(main())
