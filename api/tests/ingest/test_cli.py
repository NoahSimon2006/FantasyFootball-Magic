"""The ingest CLI (`python -m app.ingest`): argument parsing and wiring.

Nothing real is opened. `open_client` returns a SleeperClient on a fake transport, and
`session_scope` yields a session chosen by the test. The commands that run this package's
own jobs (players, projections, stats) write to the rolled-back test database. For seed,
crawl and trades, the crawler's job functions are replaced by recorders, and each test
checks the arguments the CLI passed them.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import httpx2
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Player, ProjectionSnapshot
from app.ingest import __main__ as cli
from app.ingest.crawl import SeedResult
from app.sleeper.client import SleeperClient
from tests.ingest.fake_sleeper_basic import (
    NFL_STATE_PATH,
    PLAYERS_PATH,
    FakeSleeper,
    make_client,
    nfl_state,
    players_dump,
    projections_path,
    sleeper_player,
    sleeper_projection,
)

# Late on a UTC day, so the snapshot date really comes from this pinned clock.
NOW = datetime(2026, 10, 15, 23, 30, tzinfo=UTC)


class Recorder:
    """Stands in for a job function: records every call and returns `result`."""

    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        return self.result


@pytest.fixture(autouse=True)
def no_logging_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() sets up logging for a terminal. In tests that would change the httpx2 logger's
    level for every later test, and pytest already captures the log."""
    monkeypatch.setattr(cli, "configure_logging", lambda: None)


@pytest.fixture(autouse=True)
def pinned_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "utc_now", lambda: NOW)


@pytest.fixture
def sleeper() -> FakeSleeper:
    """What Sleeper answers in this test. It starts out knowing the NFL state (2026, week 6)."""
    return FakeSleeper({NFL_STATE_PATH: nfl_state(season=2026, week=6)})


@pytest.fixture(autouse=True)
def client(sleeper: FakeSleeper, monkeypatch: pytest.MonkeyPatch) -> Iterator[SleeperClient]:
    """The client main() opens: a real SleeperClient wired to `sleeper`. Autouse, so no test
    can reach the real Sleeper API."""
    client = make_client(sleeper)
    monkeypatch.setattr(cli, "open_client", lambda: client)
    yield client
    client.close()


def use_session(monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
    """Make main()'s session_scope() yield `session` instead of opening the dev database."""

    @contextmanager
    def session_scope() -> Iterator[Session]:
        yield session

    monkeypatch.setattr(cli, "session_scope", session_scope)


@pytest.fixture
def db(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """main() works in the test's rolled-back database session."""
    use_session(monkeypatch, db_session)
    return db_session


@pytest.fixture
def no_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """main() gets a session bound to no database, so any query would fail the test."""
    session = Session()
    use_session(monkeypatch, session)
    yield session
    session.close()


def use_seed_usernames(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Set SLEEPER_SEED_USERNAMES for this test only; api/.env and the environment are ignored."""
    settings = Settings(_env_file=None, sleeper_seed_usernames=value)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)


# --- players, projections, stats: run for real against the test database ------------------


def test_players_command_writes_players_to_the_database(sleeper: FakeSleeper, db: Session) -> None:
    sleeper.routes[PLAYERS_PATH] = players_dump(
        sleeper_player("1", position="QB"), sleeper_player("2", position="RB")
    )

    exit_code = cli.main(["players"])

    assert (exit_code, db.scalar(select(func.count()).select_from(Player))) == (0, 2)


def test_players_command_stamps_rows_with_the_run_time(sleeper: FakeSleeper, db: Session) -> None:
    sleeper.routes[PLAYERS_PATH] = players_dump(sleeper_player("1"))

    cli.main(["players"])

    assert db.scalar(select(Player.updated_at)) == NOW


def test_projections_command_defaults_to_this_week_through_week_18(
    sleeper: FakeSleeper, db: Session
) -> None:
    for week in range(1, 19):
        sleeper.routes[projections_path(2026, week)] = [sleeper_projection("1", week=week)]

    cli.main(["projections"])

    assert sleeper.requested == [
        NFL_STATE_PATH,
        *(projections_path(2026, week) for week in range(6, 19)),
    ]


def test_projections_command_for_another_season_starts_at_week_1(
    sleeper: FakeSleeper, db: Session
) -> None:
    for week in range(1, 19):
        sleeper.routes[projections_path(2025, week)] = [
            sleeper_projection("1", season=2025, week=week)
        ]

    cli.main(["projections", "--season", "2025"])

    assert sleeper.requested == [
        NFL_STATE_PATH,
        *(projections_path(2025, week) for week in range(1, 19)),
    ]


def test_projections_command_with_season_and_weeks_given_skips_the_state_lookup(
    sleeper: FakeSleeper, db: Session
) -> None:
    for week in (3, 4):
        sleeper.routes[projections_path(2025, week)] = [
            sleeper_projection("1", season=2025, week=week)
        ]

    cli.main(["projections", "--season", "2025", "--from-week", "3", "--to-week", "4"])

    assert sleeper.requested == [projections_path(2025, 3), projections_path(2025, 4)]


def test_projections_command_snapshots_under_todays_utc_date(
    sleeper: FakeSleeper, db: Session
) -> None:
    sleeper.routes[projections_path(2026, 6)] = [sleeper_projection("1")]

    cli.main(["projections", "--to-week", "6"])

    assert db.scalar(select(ProjectionSnapshot.snapshot_date)) == NOW.date()


def test_projections_command_rejects_a_from_week_after_the_to_week(no_db: Session) -> None:
    argv = ["projections", "--season", "2026", "--from-week", "10", "--to-week", "5"]

    assert cli.main(argv) == 1


def test_stats_command_prints_the_report_to_stdout(
    db: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["stats"])

    assert "Trades by league type" in capsys.readouterr().out


# --- seed, crawl, trades: the crawler's job functions are replaced by recorders ------------


def test_seed_command_seeds_the_configured_usernames(
    client: SleeperClient, no_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_users = Recorder(SeedResult(resolved=2, unknown=[]))
    monkeypatch.setattr("app.ingest.crawl.seed_users", seed_users)
    use_seed_usernames(monkeypatch, "alice, bob")

    cli.main(["seed"])

    assert seed_users.calls == [((no_db, client, ["alice", "bob"]), {})]


def test_seed_command_without_usernames_fails_naming_the_setting(
    no_db: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("app.ingest.crawl.seed_users", Recorder(SeedResult(resolved=0, unknown=[])))
    use_seed_usernames(monkeypatch, "")

    exit_code = cli.main(["seed"])

    assert exit_code == 1 and "SLEEPER_SEED_USERNAMES" in caplog.text


def test_seed_command_fails_when_sleeper_knows_none_of_the_usernames(
    no_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_users = Recorder(SeedResult(resolved=0, unknown=["alice"]))
    monkeypatch.setattr("app.ingest.crawl.seed_users", seed_users)
    use_seed_usernames(monkeypatch, "alice")

    assert cli.main(["seed"]) == 1


def test_crawl_command_defaults_to_the_current_and_previous_seasons(
    client: SleeperClient, no_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    crawl_leagues = Recorder(result="crawl stats")
    monkeypatch.setattr("app.ingest.crawl.crawl_leagues", crawl_leagues)

    cli.main(["crawl"])

    assert crawl_leagues.calls == [
        ((no_db, client), {"seasons": [2026, 2025], "max_requests": 1500})
    ]


def test_crawl_command_passes_the_given_seasons_and_budget(
    client: SleeperClient, no_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    crawl_leagues = Recorder(result="crawl stats")
    monkeypatch.setattr("app.ingest.crawl.crawl_leagues", crawl_leagues)

    cli.main(["crawl", "--seasons", "2024", "2023", "--max-requests", "50"])

    assert crawl_leagues.calls == [((no_db, client), {"seasons": [2024, 2023], "max_requests": 50})]


def test_trades_command_in_the_current_season_counts_only_past_weeks_as_complete(
    client: SleeperClient, no_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingest_trades = Recorder(result="trade stats")
    monkeypatch.setattr("app.ingest.trades.ingest_trades", ingest_trades)

    cli.main(["trades"])

    assert ingest_trades.calls == [
        (
            (no_db, client),
            {
                "season": 2026,
                "through_week": 6,
                "completed_through_week": 5,
                "max_requests": 3000,
                "league_type": 0,
            },
        )
    ]


def test_trades_command_for_a_past_season_covers_all_18_weeks(
    client: SleeperClient, no_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingest_trades = Recorder(result="trade stats")
    monkeypatch.setattr("app.ingest.trades.ingest_trades", ingest_trades)

    cli.main(["trades", "--season", "2025", "--max-requests", "100"])

    assert ingest_trades.calls == [
        (
            (no_db, client),
            {
                "season": 2025,
                "through_week": 18,
                "completed_through_week": 18,
                "max_requests": 100,
                "league_type": 0,
            },
        )
    ]


def test_trades_command_can_sample_another_league_type(
    client: SleeperClient, no_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingest_trades = Recorder(result="trade stats")
    monkeypatch.setattr("app.ingest.trades.ingest_trades", ingest_trades)

    cli.main(["trades", "--league-type", "2", "--max-requests", "60"])

    _, kwargs = ingest_trades.calls[0]
    assert (kwargs["league_type"], kwargs["max_requests"]) == (2, 60)


def test_trades_command_rejects_an_unknown_league_type() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["trades", "--league-type", "7"])

    assert excinfo.value.code == 2


# --- Outcomes: log lines and exit codes -----------------------------------------------------


def test_finished_command_logs_a_summary_with_the_sleeper_request_count(
    sleeper: FakeSleeper, db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    sleeper.routes[PLAYERS_PATH] = players_dump(sleeper_player("1"))
    caplog.set_level(logging.INFO, logger="app.ingest")

    cli.main(["players"])

    assert "players done | players upserted: 1 | Sleeper requests: 1 |" in caplog.text


def test_sleeper_error_exits_with_1_and_logs_the_reason_in_one_line(
    sleeper: FakeSleeper, no_db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    sleeper.routes[PLAYERS_PATH] = httpx2.Response(403)

    exit_code = cli.main(["players"])

    assert exit_code == 1
    assert "players failed | Sleeper /players/nfl returned HTTP 403" in caplog.text


def test_unknown_command_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["dance"])

    assert excinfo.value.code == 2
