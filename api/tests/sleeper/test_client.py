import logging
import os
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest

from app.sleeper.client import (
    SleeperClient,
    SleeperError,
    SleeperParseError,
    SleeperUnavailableError,
)
from app.sleeper.models import DraftPickMove, FaabMove, SleeperUser
from tests.sleeper.helpers import FakeTime, ScriptedSleeper, json_response, load_fixture

# The anonymized ids the fixtures were saved with.
OWNER_ID = "100000000000000001"
LEAGUE_ID = "900000000000000001"
UNKNOWN_ID = "999999999999999999"

Handler = Callable[[httpx2.Request], httpx2.Response]
ClientFactory = Callable[..., SleeperClient]


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
def make_client(fake_time: FakeTime) -> Iterator[ClientFactory]:
    """Builds clients on a mock transport and fake time, and closes them after the test."""
    clients: list[SleeperClient] = []

    def make(handler: Handler, **options: Any) -> SleeperClient:
        client = SleeperClient(
            transport=httpx2.MockTransport(handler),
            sleep=fake_time.sleep,
            clock=fake_time.clock,
            **options,
        )
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()


def serve(routes: dict[str, Any]) -> Handler:
    """Answers each `host/path` key with its JSON payload; any other URL fails the test."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        key = f"{request.url.host}{request.url.path}"
        if key not in routes:
            raise AssertionError(f"unexpected request: {request.url}")
        return json_response(routes[key])

    return handler


def nfl_state_response() -> httpx2.Response:
    return json_response(load_fixture("nfl_state.json"))


def make_trade(**changes: Any) -> dict[str, Any]:
    """The first real trade in the trade fixture, with some fields replaced."""
    trade = next(tx for tx in load_fixture("transactions_trade.json") if tx["type"] == "trade")
    return {**trade, **changes}


# --- Real responses parse through their client methods -----------------------------------

LIST_ENDPOINTS: list[tuple[str, str, Callable[[SleeperClient], list[Any]]]] = [
    (
        f"api.sleeper.app/v1/user/{OWNER_ID}/leagues/nfl/2026",
        "user_leagues.json",
        lambda client: client.get_user_leagues(OWNER_ID, 2026),
    ),
    (
        f"api.sleeper.app/v1/league/{LEAGUE_ID}/users",
        "league_users.json",
        lambda client: client.get_league_users(LEAGUE_ID),
    ),
    (
        f"api.sleeper.app/v1/league/{LEAGUE_ID}/rosters",
        "league_rosters.json",
        lambda client: client.get_league_rosters(LEAGUE_ID),
    ),
    (
        f"api.sleeper.app/v1/league/{LEAGUE_ID}/transactions/2",
        "transactions_trade.json",
        lambda client: client.get_transactions(LEAGUE_ID, 2),
    ),
    (
        f"api.sleeper.app/v1/league/{LEAGUE_ID}/transactions/1",
        "transactions_no_trade.json",
        lambda client: client.get_transactions(LEAGUE_ID, 1),
    ),
    (
        "api.sleeper.com/projections/nfl/2026/6",
        "projections_week.json",
        lambda client: client.get_weekly_projections(2026, 6),
    ),
]


@pytest.mark.parametrize(
    ("url", "fixture", "call"), LIST_ENDPOINTS, ids=[fixture for _, fixture, _ in LIST_ENDPOINTS]
)
def test_every_item_of_a_real_list_response_validates(
    make_client: ClientFactory,
    url: str,
    fixture: str,
    call: Callable[[SleeperClient], list[Any]],
) -> None:
    raw = load_fixture(fixture)
    client = make_client(serve({url: raw}))

    assert len(call(client)) == len(raw)


def test_get_nfl_state_parses_real_response(make_client: ClientFactory) -> None:
    client = make_client(serve({"api.sleeper.app/v1/state/nfl": load_fixture("nfl_state.json")}))

    state = client.get_nfl_state()

    # Sleeper sends seasons as strings ("2026"); the model turns them into ints.
    assert (state.season, state.previous_season, state.week, state.season_type) == (
        2026,
        2025,
        6,
        "regular",
    )


def test_get_user_parses_real_response(make_client: ClientFactory) -> None:
    client = make_client(serve({"api.sleeper.app/v1/user/test_user": load_fixture("user.json")}))

    assert client.get_user("test_user") == SleeperUser(user_id=OWNER_ID, username="test_user")


def test_get_user_leagues_reads_scoring_format_from_real_league(make_client: ClientFactory) -> None:
    url = f"api.sleeper.app/v1/user/{OWNER_ID}/leagues/nfl/2026"
    client = make_client(serve({url: load_fixture("user_leagues.json")}))

    [league] = client.get_user_leagues(OWNER_ID, 2026)

    # The owner's league: 12-team, full PPR, one QB, redraft (settings.type 0).
    assert (league.total_rosters, league.ppr, league.is_superflex, league.league_type) == (
        12,
        1.0,
        False,
        0,
    )


def test_get_league_parses_real_response(make_client: ClientFactory) -> None:
    url = f"api.sleeper.app/v1/league/{LEAGUE_ID}"
    client = make_client(serve({url: load_fixture("league.json")}))

    league = client.get_league(LEAGUE_ID)

    assert league is not None
    assert (league.league_id, league.season, league.status, league.settings.trade_deadline) == (
        LEAGUE_ID,
        2026,
        "in_season",
        11,
    )


def test_get_league_users_parses_real_response(make_client: ClientFactory) -> None:
    url = f"api.sleeper.app/v1/league/{LEAGUE_ID}/users"
    client = make_client(serve({url: load_fixture("league_users.json")}))

    users = client.get_league_users(LEAGUE_ID)

    assert OWNER_ID in {user.user_id for user in users}


def test_get_league_rosters_links_rosters_to_owners(make_client: ClientFactory) -> None:
    url = f"api.sleeper.app/v1/league/{LEAGUE_ID}/rosters"
    client = make_client(serve({url: load_fixture("league_rosters.json")}))

    rosters = client.get_league_rosters(LEAGUE_ID)

    owner_roster = next(roster for roster in rosters if roster.owner_id == OWNER_ID)
    assert (owner_roster.roster_id, len(owner_roster.players or [])) == (9, 17)


def test_get_transactions_parses_a_real_trade(make_client: ClientFactory) -> None:
    url = f"api.sleeper.app/v1/league/{LEAGUE_ID}/transactions/2"
    client = make_client(serve({url: load_fixture("transactions_trade.json")}))

    transactions = client.get_transactions(LEAGUE_ID, 2)

    trade = next(tx for tx in transactions if tx.transaction_id == "1407974116450992128")
    # `adds` maps each player to the roster that RECEIVES him.
    assert (trade.type, trade.roster_ids, trade.adds) == (
        "trade",
        [2, 9],
        {"11564": 2, "5001": 2, "7553": 9, "9758": 9},
    )


def test_get_transactions_parses_a_real_week_without_trades(make_client: ClientFactory) -> None:
    url = f"api.sleeper.app/v1/league/{LEAGUE_ID}/transactions/1"
    client = make_client(serve({url: load_fixture("transactions_no_trade.json")}))

    transactions = client.get_transactions(LEAGUE_ID, 1)

    assert {tx.type for tx in transactions} == {"waiver", "free_agent"}


def test_trade_with_draft_picks_and_faab_parses(make_client: ClientFactory) -> None:
    # No real trade in our fixtures moved picks or FAAB, so this uses the shape from
    # Sleeper's API docs (pick seasons arrive as strings).
    trade = make_trade(
        draft_picks=[
            {"season": "2027", "round": 1, "roster_id": 2, "previous_owner_id": 2, "owner_id": 9}
        ],
        waiver_budget=[{"sender": 9, "receiver": 2, "amount": 15}],
    )
    client = make_client(ScriptedSleeper(json_response([trade])))

    [parsed] = client.get_transactions(LEAGUE_ID, 2)

    assert (parsed.draft_picks, parsed.waiver_budget) == (
        [DraftPickMove(season=2027, round=1, roster_id=2, previous_owner_id=2, owner_id=9)],
        [FaabMove(sender=9, receiver=2, amount=15)],
    )


def test_get_players_parses_real_subset_keyed_by_player_id(make_client: ClientFactory) -> None:
    raw = load_fixture("players_subset.json")
    client = make_client(serve({"api.sleeper.app/v1/players/nfl": raw}))

    players = client.get_players()

    assert list(players) == list(raw)


def test_team_defense_gets_a_display_name_without_full_name(make_client: ClientFactory) -> None:
    client = make_client(ScriptedSleeper(json_response(load_fixture("players_subset.json"))))

    players = client.get_players()

    assert players["DEN"].display_name == "Denver Broncos"


def test_get_weekly_projections_parses_real_rows(make_client: ClientFactory) -> None:
    url = "api.sleeper.com/projections/nfl/2026/6"
    client = make_client(serve({url: load_fixture("projections_week.json")}))

    rows = client.get_weekly_projections(2026, 6)

    assert (rows[0].player_id, rows[0].season, rows[0].pts_ppr) == ("9509", 2026, 26.3)


def test_get_weekly_projections_asks_for_the_requested_positions(
    make_client: ClientFactory,
) -> None:
    sleeper = ScriptedSleeper(json_response([]))
    client = make_client(sleeper)

    client.get_weekly_projections(2026, 6, positions=("QB", "TE"))

    params = sleeper.requests[0].url.params
    assert (params.get_list("position[]"), params["season_type"]) == (["QB", "TE"], "regular")


# --- Things that don't exist: null bodies and 404s ----------------------------------------


def test_get_user_returns_none_for_an_unknown_username(make_client: ClientFactory) -> None:
    # What real Sleeper does: HTTP 200 with the body `null`.
    client = make_client(ScriptedSleeper(json_response(None)))

    assert client.get_user("no_such_user_zz9") is None


def test_get_league_returns_none_for_an_unknown_league(make_client: ClientFactory) -> None:
    # What real Sleeper does: HTTP 404 with the body `null`.
    client = make_client(ScriptedSleeper(json_response(None, status=404)))

    assert client.get_league(UNKNOWN_ID) is None


def test_list_endpoint_treats_a_null_body_as_empty(make_client: ClientFactory) -> None:
    client = make_client(ScriptedSleeper(json_response(None)))

    assert client.get_transactions(LEAGUE_ID, 3) == []


def test_list_endpoint_treats_404_as_empty(make_client: ClientFactory) -> None:
    # What real Sleeper does for the rosters of an unknown league.
    client = make_client(ScriptedSleeper(json_response(None, status=404)))

    assert client.get_league_rosters(UNKNOWN_ID) == []


def test_404_where_a_result_is_required_raises_without_retrying(
    make_client: ClientFactory,
) -> None:
    # The script holds one response, so a retry would fail the test.
    client = make_client(ScriptedSleeper(json_response(None, status=404)))

    with pytest.raises(SleeperError, match="404") as excinfo:
        client.get_nfl_state()

    assert excinfo.type is SleeperError


def test_other_client_errors_raise_without_retrying(make_client: ClientFactory) -> None:
    client = make_client(ScriptedSleeper(json_response({"error": "forbidden"}, status=403)))

    with pytest.raises(SleeperError, match="403") as excinfo:
        client.get_league(LEAGUE_ID)

    assert excinfo.type is SleeperError


# --- Retries --------------------------------------------------------------------------------


def test_retries_server_errors_with_exponential_backoff(
    make_client: ClientFactory, fake_time: FakeTime
) -> None:
    client = make_client(
        ScriptedSleeper(httpx2.Response(500), httpx2.Response(502), nfl_state_response())
    )

    client.get_nfl_state()

    assert fake_time.sleeps == [1.0, 2.0]


def test_retries_429_after_the_retry_after_delay(
    make_client: ClientFactory, fake_time: FakeTime
) -> None:
    client = make_client(
        ScriptedSleeper(httpx2.Response(429, headers={"Retry-After": "7"}), nfl_state_response())
    )

    client.get_nfl_state()

    assert fake_time.sleeps == [7.0]


@pytest.mark.parametrize(
    "retry_after",
    ["Wed, 14 Oct 2026 23:40:00 GMT", "-5", "nan"],
    ids=["http-date", "negative", "nan"],
)
def test_unusable_retry_after_falls_back_to_backoff(
    make_client: ClientFactory, fake_time: FakeTime, retry_after: str
) -> None:
    rate_limited = httpx2.Response(429, headers={"Retry-After": retry_after})
    client = make_client(ScriptedSleeper(rate_limited, nfl_state_response()))

    client.get_nfl_state()

    assert fake_time.sleeps == [1.0]


def test_huge_retry_after_is_capped_so_a_crawl_cannot_stall(
    make_client: ClientFactory, fake_time: FakeTime
) -> None:
    rate_limited = httpx2.Response(429, headers={"Retry-After": "3600"})
    client = make_client(ScriptedSleeper(rate_limited, nfl_state_response()))

    client.get_nfl_state()

    assert fake_time.sleeps == [60.0]


@pytest.mark.parametrize(
    "error",
    [
        httpx2.ReadTimeout("timed out"),
        httpx2.ConnectError("connection refused"),
        httpx2.RemoteProtocolError("server disconnected without sending a response"),
    ],
    ids=["timeout", "connect-error", "dropped-connection"],
)
def test_recovers_from_timeouts_and_connection_errors(
    make_client: ClientFactory, error: Exception
) -> None:
    client = make_client(ScriptedSleeper(error, nfl_state_response()))

    assert client.get_nfl_state().week == 6


def test_gives_up_with_unavailable_error_after_max_attempts(
    make_client: ClientFactory, fake_time: FakeTime
) -> None:
    client = make_client(ScriptedSleeper(*(httpx2.Response(503) for _ in range(4))))

    with pytest.raises(SleeperUnavailableError):
        client.get_nfl_state()

    # Four attempts, with a wait between each pair and none after the last one.
    assert (client.requests_made, fake_time.sleeps) == (4, [1.0, 2.0, 4.0])


def test_requests_made_counts_every_attempt_including_retries(
    make_client: ClientFactory,
) -> None:
    client = make_client(
        ScriptedSleeper(httpx2.Response(500), httpx2.Response(500), nfl_state_response())
    )

    client.get_nfl_state()

    assert client.requests_made == 3


def test_back_to_back_requests_are_spaced_by_the_rate_limiter(
    make_client: ClientFactory, fake_time: FakeTime
) -> None:
    client = make_client(
        ScriptedSleeper(nfl_state_response(), nfl_state_response()), max_requests_per_minute=60
    )

    client.get_nfl_state()
    client.get_nfl_state()

    assert fake_time.sleeps == [1.0]


# --- Validation -----------------------------------------------------------------------------


def leagues_with_one_broken() -> list[dict[str, Any]]:
    [valid] = load_fixture("user_leagues.json")
    broken = {**valid, "league_id": "900000000000000099", "total_rosters": "twelve"}
    return [broken, valid]


def test_invalid_league_is_skipped_while_valid_ones_return(make_client: ClientFactory) -> None:
    client = make_client(ScriptedSleeper(json_response(leagues_with_one_broken())))

    leagues = client.get_user_leagues(OWNER_ID, 2026)

    assert [league.league_id for league in leagues] == [LEAGUE_ID]


def test_skipped_league_is_logged_as_a_warning_with_endpoint_and_id(
    make_client: ClientFactory, caplog: pytest.LogCaptureFixture
) -> None:
    client = make_client(ScriptedSleeper(json_response(leagues_with_one_broken())))

    with caplog.at_level(logging.WARNING, logger="app.sleeper.client"):
        client.get_user_leagues(OWNER_ID, 2026)

    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert f"/user/{OWNER_ID}/leagues/nfl/2026" in record.getMessage()
    assert "900000000000000099" in record.getMessage()


def test_invalid_single_object_raises_parse_error_naming_the_endpoint(
    make_client: ClientFactory,
) -> None:
    client = make_client(ScriptedSleeper(json_response({"league_id": LEAGUE_ID})))

    with pytest.raises(SleeperParseError, match=f"/league/{LEAGUE_ID}"):
        client.get_league(LEAGUE_ID)


def test_body_that_is_not_json_raises_parse_error(make_client: ClientFactory) -> None:
    client = make_client(ScriptedSleeper(httpx2.Response(200, text="<html>Maintenance</html>")))

    with pytest.raises(SleeperParseError):
        client.get_nfl_state()


def test_username_cannot_redirect_the_request_to_another_endpoint(
    make_client: ClientFactory,
) -> None:
    sleeper = ScriptedSleeper(json_response(None))
    client = make_client(sleeper)

    client.get_user("../players/nfl")

    assert sleeper.requests[0].url.raw_path == b"/v1/user/..%2Fplayers%2Fnfl"


# --- Players cache --------------------------------------------------------------------------


def test_fresh_players_cache_is_reused_without_an_http_request(
    make_client: ClientFactory, tmp_path: Path
) -> None:
    downloader = make_client(
        ScriptedSleeper(json_response(load_fixture("players_subset.json"))), cache_dir=tmp_path
    )
    downloaded = downloader.get_players()
    # A later client on the same cache has no scripted responses: any request fails the test.
    reader = make_client(ScriptedSleeper(), cache_dir=tmp_path)

    assert reader.get_players() == downloaded


def test_players_cache_older_than_a_day_is_downloaded_again(
    make_client: ClientFactory, tmp_path: Path
) -> None:
    cache_file = tmp_path / "players_nfl.json"
    cache_file.write_text("{}", encoding="utf-8")
    twenty_five_hours_ago = time.time() - 25 * 60 * 60
    os.utime(cache_file, (twenty_five_hours_ago, twenty_five_hours_ago))
    raw = load_fixture("players_subset.json")
    client = make_client(ScriptedSleeper(json_response(raw)), cache_dir=tmp_path)

    assert len(client.get_players()) == len(raw)


def test_unreadable_players_cache_is_downloaded_again(
    make_client: ClientFactory, tmp_path: Path
) -> None:
    (tmp_path / "players_nfl.json").write_text('{"4984": {"player_id"', encoding="utf-8")
    raw = load_fixture("players_subset.json")
    client = make_client(ScriptedSleeper(json_response(raw)), cache_dir=tmp_path)

    assert len(client.get_players()) == len(raw)


def test_failing_to_write_the_cache_still_returns_the_download(
    make_client: ClientFactory, tmp_path: Path
) -> None:
    not_a_directory = tmp_path / "cache"
    not_a_directory.write_text("a file where the cache directory should be", encoding="utf-8")
    raw = load_fixture("players_subset.json")
    client = make_client(ScriptedSleeper(json_response(raw)), cache_dir=not_a_directory)

    assert len(client.get_players()) == len(raw)
