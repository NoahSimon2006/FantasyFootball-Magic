"""The one Sleeper API client.

Every call to Sleeper goes through `SleeperClient`, which owns the cross-cutting concerns:
rate limiting, retries with exponential backoff, parsing raw JSON into the Pydantic models in
`app.sleeper.models`, and the once-a-day disk cache for the multi-MB players map. Raw dicts
never leave this module.
"""

import json
import logging
import math
import os
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx2
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.sleeper.models import (
    NflState,
    ProjectionRow,
    SleeperLeague,
    SleeperLeagueUser,
    SleeperPlayer,
    SleeperRoster,
    SleeperTransaction,
    SleeperUser,
)
from app.sleeper.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.sleeper.app/v1"
# The projections endpoint is unofficial and lives on a different host. Only
# `get_weekly_projections` touches it, so it can be swapped for another source.
PROJECTIONS_BASE_URL = "https://api.sleeper.com"
USER_AGENT = "fantasy-magic/0.1"

BACKOFF_BASE_SECONDS = 1.0  # waits of 1s, 2s, 4s, ... between attempts
MAX_BACKOFF_SECONDS = 60.0  # also caps Retry-After, so one odd header can't stall a crawl
# Transient failures worth another try. Other transport errors (bad proxy, unsupported
# protocol) would fail the same way again, so they are raised immediately.
RETRYABLE_ERRORS = (httpx2.TimeoutException, httpx2.NetworkError, httpx2.RemoteProtocolError)

PLAYERS_CACHE_FILE = "players_nfl.json"
PLAYERS_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60  # Sleeper asks for at most one call per day


class SleeperError(Exception):
    """Base class for every failure talking to Sleeper."""


class SleeperUnavailableError(SleeperError):
    """Sleeper kept failing (429, 5xx, timeout, connection error) until retries ran out."""


class SleeperParseError(SleeperError):
    """A response didn't have the shape we expect. The message names the endpoint."""


class SleeperClient:
    """Synchronous Sleeper API client. Use it as a context manager, or call `close()`.

    `sleep` and `clock` are injectable so tests can run the retry and rate-limit logic
    without real waiting.
    """

    def __init__(
        self,
        *,
        max_requests_per_minute: int = 600,
        max_attempts: int = 4,
        timeout: float = 15.0,
        cache_dir: Path | None = None,
        transport: httpx2.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be at least 1, got {max_attempts}")
        # Every HTTP attempt, retries included: the crawler budgets against this number.
        self.requests_made = 0
        self._max_attempts = max_attempts
        self._cache_dir = cache_dir
        self._sleep = sleep
        self._limiter = RateLimiter(max_requests_per_minute, clock=clock, sleep=sleep)
        self._counter_lock = threading.Lock()
        self._http = httpx2.Client(
            timeout=timeout,
            transport=transport,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            max_requests_per_minute=settings.sleeper_max_requests_per_minute,
            cache_dir=settings.cache_dir,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # --- Endpoints ---------------------------------------------------------------------

    def get_nfl_state(self) -> NflState:
        path = "/state/nfl"
        return _parse_one(NflState, self._get_json(path, allow_not_found=False), path)

    def get_user(self, username_or_id: str) -> SleeperUser | None:
        """`None` for an unknown user (Sleeper answers HTTP 200 with a `null` body)."""
        path = f"/user/{_segment(username_or_id)}"
        data = self._get_json(path)
        return None if data is None else _parse_one(SleeperUser, data, path)

    def get_user_leagues(self, user_id: str, season: int) -> list[SleeperLeague]:
        path = f"/user/{_segment(user_id)}/leagues/nfl/{season}"
        return _parse_items(SleeperLeague, self._get_json(path), path, "league_id")

    def get_league(self, league_id: str) -> SleeperLeague | None:
        """`None` for an unknown league (Sleeper answers HTTP 404 with a `null` body)."""
        path = f"/league/{_segment(league_id)}"
        data = self._get_json(path)
        return None if data is None else _parse_one(SleeperLeague, data, path)

    def get_league_users(self, league_id: str) -> list[SleeperLeagueUser]:
        path = f"/league/{_segment(league_id)}/users"
        return _parse_items(SleeperLeagueUser, self._get_json(path), path, "user_id")

    def get_league_rosters(self, league_id: str) -> list[SleeperRoster]:
        path = f"/league/{_segment(league_id)}/rosters"
        return _parse_items(SleeperRoster, self._get_json(path), path, "roster_id")

    def get_transactions(self, league_id: str, week: int) -> list[SleeperTransaction]:
        path = f"/league/{_segment(league_id)}/transactions/{week}"
        return _parse_items(SleeperTransaction, self._get_json(path), path, "transaction_id")

    def get_players(self) -> dict[str, SleeperPlayer]:
        """Every NFL player, keyed by player_id (about 15 MB from Sleeper).

        With a `cache_dir`, the download is reused for 24 hours, because Sleeper asks clients
        to fetch this map at most once per day.
        """
        path = "/players/nfl"
        data = self._read_players_cache()
        if data is None:
            fetched = self._get_json(path, allow_not_found=False)
            if not isinstance(fetched, dict):
                raise SleeperParseError(
                    f"Sleeper {path} returned {type(fetched).__name__}, expected an object"
                )
            self._write_players_cache(fetched)
            data = fetched
        players = _parse_items(SleeperPlayer, list(data.values()), path, "player_id")
        return {player.player_id: player for player in players}

    def get_weekly_projections(
        self,
        season: int,
        week: int,
        positions: Sequence[str] = ("QB", "RB", "WR", "TE"),
    ) -> list[ProjectionRow]:
        """Regular-season projections for one week, from Sleeper's UNOFFICIAL endpoint.

        Kept self-contained so another projections source can replace it without touching
        callers.
        """
        path = f"/projections/nfl/{season}/{week}"
        params = httpx2.QueryParams(
            [
                ("season_type", "regular"),
                *(("position[]", position) for position in positions),
                ("order_by", "pts_ppr"),
            ]
        )
        data = self._get_json(path, base_url=PROJECTIONS_BASE_URL, params=params)
        return _parse_items(ProjectionRow, data, path, "player_id")

    # --- Transport ---------------------------------------------------------------------

    def _get_json(
        self,
        path: str,
        *,
        base_url: str = API_BASE_URL,
        params: httpx2.QueryParams | None = None,
        allow_not_found: bool = True,
    ) -> Any:  # Any: decoded JSON of unknown shape; callers validate it immediately.
        """Decoded JSON body, or `None` for a 404 when `allow_not_found` is set."""
        response = self._request(f"{base_url}{path}", path, params)
        if response.status_code == 404:
            if allow_not_found:
                return None
            raise SleeperError(f"Sleeper {path} returned HTTP 404")
        try:
            return response.json()
        except ValueError as exc:  # JSONDecodeError, or a body that isn't valid UTF-8
            raise SleeperParseError(f"Sleeper {path} returned a body that isn't JSON") from exc

    def _request(
        self, url: str, endpoint: str, params: httpx2.QueryParams | None
    ) -> httpx2.Response:
        """GET through the rate limiter, retrying transient failures.

        Returns any 2xx or 404 response. Other 4xx responses mean the request itself is wrong,
        so they raise `SleeperError` at once; 429, 5xx, timeouts and connection errors are
        retried with exponential backoff until `max_attempts` is used up.
        """
        last_failure = ""
        last_error: httpx2.TransportError | None = None
        for attempt in range(1, self._max_attempts + 1):
            self._limiter.acquire()
            with self._counter_lock:
                self.requests_made += 1
            retry_after: float | None = None
            try:
                response = self._http.get(url, params=params)
            except RETRYABLE_ERRORS as exc:
                last_failure, last_error = f"{type(exc).__name__}: {exc}", exc
            except httpx2.RequestError as exc:
                raise SleeperError(f"Sleeper {endpoint} request failed: {exc!r}") from exc
            else:
                status = response.status_code
                if response.is_success or status == 404:
                    return response
                if status != 429 and status < 500:
                    raise SleeperError(f"Sleeper {endpoint} returned HTTP {status}")
                last_failure, last_error = f"HTTP {status}", None
                retry_after = _retry_after_seconds(response)
            if attempt < self._max_attempts:
                delay = retry_after if retry_after is not None else _backoff_seconds(attempt)
                logger.warning(
                    "Sleeper %s failed (%s) on attempt %d of %d; retrying in %.1fs",
                    endpoint,
                    last_failure,
                    attempt,
                    self._max_attempts,
                    delay,
                )
                self._sleep(delay)
        raise SleeperUnavailableError(
            f"Sleeper {endpoint} still failing after {self._max_attempts} attempts "
            f"(last: {last_failure})"
        ) from last_error

    # --- Players cache -----------------------------------------------------------------

    def _read_players_cache(self) -> dict[str, Any] | None:
        """The cached raw players map if it is under a day old; otherwise `None`."""
        if self._cache_dir is None:
            return None
        path = self._cache_dir / PLAYERS_CACHE_FILE
        try:
            if time.time() - path.stat().st_mtime >= PLAYERS_CACHE_MAX_AGE_SECONDS:
                return None
            data = json.loads(path.read_bytes())
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable players cache %s: %s", path, exc)
            return None
        if not isinstance(data, dict):
            logger.warning("Ignoring players cache %s: it holds a %s", path, type(data).__name__)
            return None
        return data

    def _write_players_cache(self, data: dict[str, Any]) -> None:
        if self._cache_dir is None:
            return
        path = self._cache_dir / PLAYERS_CACHE_FILE
        temp_path = path.with_name(f"{path.name}.tmp")
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(json.dumps(data), encoding="utf-8")
            # Atomic swap: a crash mid-write can't leave a truncated cache behind.
            os.replace(temp_path, path)
        except OSError as exc:
            # The download itself succeeded; losing the cache only costs a refetch next time.
            logger.warning("Could not write players cache %s: %s", path, exc)


def _segment(value: str) -> str:
    """Percent-encode one URL path segment, so input like `../players/nfl` can't change
    which endpoint gets called."""
    return quote(value, safe="")


def _backoff_seconds(failed_attempt: int) -> float:
    return min(BACKOFF_BASE_SECONDS * 2.0 ** (failed_attempt - 1), MAX_BACKOFF_SECONDS)


def _retry_after_seconds(response: httpx2.Response) -> float | None:
    """Seconds from a numeric `Retry-After` header (capped), or `None` to use normal backoff.

    The HTTP-date form of the header isn't supported; it falls back to backoff too.
    """
    header = response.headers.get("Retry-After")
    if header is None:
        return None
    try:
        seconds = float(header)
    except ValueError:
        return None
    if not math.isfinite(seconds) or seconds < 0:
        return None
    return min(seconds, MAX_BACKOFF_SECONDS)


def _describe(exc: ValidationError) -> str:
    """`field: problem` pairs, without the offending input values (they can be large)."""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
        for error in exc.errors()
    )


def _parse_one[M: BaseModel](model: type[M], data: Any, endpoint: str) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise SleeperParseError(
            f"Sleeper {endpoint} returned an unexpected {model.__name__}: {_describe(exc)}"
        ) from exc


def _parse_items[M: BaseModel](model: type[M], data: Any, endpoint: str, id_field: str) -> list[M]:
    """Validate a list response item by item.

    An invalid item is logged and skipped, so one odd league or transaction can't sink a whole
    crawl. Sleeper sometimes sends `null` where it means an empty list.
    """
    if data is None:
        return []
    if not isinstance(data, list):
        raise SleeperParseError(
            f"Sleeper {endpoint} returned {type(data).__name__}, expected a list"
        )
    items: list[M] = []
    for raw in data:
        try:
            items.append(model.model_validate(raw))
        except ValidationError as exc:
            item_id = raw.get(id_field) if isinstance(raw, dict) else None
            logger.warning(
                "Skipping invalid %s from Sleeper %s (%s=%s): %s",
                model.__name__,
                endpoint,
                id_field,
                item_id,
                _describe(exc),
            )
    return items
