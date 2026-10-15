"""Typed views of Sleeper API responses.

Sleeper's API is only partly documented and changes without notice, so every response is
parsed here, at the edge of the app. Unknown fields are ignored; a missing *required* field
fails loudly. Only the fields this project uses are declared.
"""

from datetime import UTC, datetime

from pydantic import BaseModel


class NflState(BaseModel):
    """`GET /state/nfl`: where the NFL calendar is right now."""

    season: int
    week: int
    season_type: str  # "pre" | "regular" | "post" | "off"
    previous_season: int
    display_week: int


class SleeperUser(BaseModel):
    """`GET /user/<username or user_id>`. We keep only the id (data minimization)."""

    user_id: str
    username: str | None = None


class LeagueSettings(BaseModel):
    # Undocumented: 0 = redraft, 1 = keeper, 2 = dynasty (owner's redraft league is 0;
    # the crawler validates this across many leagues before we rely on it).
    type: int | None = None
    trade_deadline: int | None = None


class SleeperLeague(BaseModel):
    """One element of `GET /user/<user_id>/leagues/nfl/<season>`, or `GET /league/<id>`."""

    league_id: str
    season: int
    status: str  # "pre_draft" | "drafting" | "in_season" | "complete"
    total_rosters: int
    settings: LeagueSettings
    scoring_settings: dict[str, float | None] = {}
    roster_positions: list[str] | None = None
    previous_league_id: str | None = None

    @property
    def league_type(self) -> int | None:
        return self.settings.type

    @property
    def ppr(self) -> float:
        """Points per reception: 1.0 full PPR, 0.5 half, 0.0 standard."""
        return float(self.scoring_settings.get("rec") or 0.0)

    @property
    def is_superflex(self) -> bool:
        positions = self.roster_positions or []
        return "SUPER_FLEX" in positions or positions.count("QB") >= 2


class SleeperLeagueUser(BaseModel):
    """One element of `GET /league/<id>/users`. Only the id: it feeds the crawl frontier."""

    user_id: str


class SleeperRoster(BaseModel):
    """One element of `GET /league/<id>/rosters`."""

    roster_id: int
    owner_id: str | None = None
    players: list[str] | None = None


class DraftPickMove(BaseModel):
    season: int  # Sleeper sends a string ("2027"); pydantic converts it
    round: int
    roster_id: int  # the roster that originally owned the pick
    previous_owner_id: int | None = None  # roster giving it up in this transaction
    owner_id: int  # roster receiving it


class FaabMove(BaseModel):
    sender: int
    receiver: int
    amount: int


class SleeperTransaction(BaseModel):
    """One element of `GET /league/<id>/transactions/<week>`."""

    transaction_id: str
    type: str  # "trade" | "waiver" | "free_agent" | "commissioner"
    status: str  # "complete" | "failed" | ...
    leg: int  # the NFL week it happened in
    created: int  # epoch milliseconds
    roster_ids: list[int]
    adds: dict[str, int] | None = None  # player_id -> roster_id that RECEIVES the player
    drops: dict[str, int] | None = None  # player_id -> roster_id that GIVES UP the player
    draft_picks: list[DraftPickMove] | None = None
    waiver_budget: list[FaabMove] | None = None  # FAAB dollars moved in a trade

    @property
    def created_at(self) -> datetime:
        return datetime.fromtimestamp(self.created / 1000, tz=UTC)


class SleeperPlayer(BaseModel):
    """One value of the `GET /players/nfl` map (keyed by player_id)."""

    player_id: str
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None  # absent for team defenses
    position: str | None = None
    team: str | None = None
    age: int | None = None
    years_exp: int | None = None
    status: str | None = None
    injury_status: str | None = None
    active: bool | None = None
    fantasy_positions: list[str] | None = None

    @property
    def display_name(self) -> str:
        if self.full_name:
            return self.full_name
        return (
            " ".join(part for part in (self.first_name, self.last_name) if part) or self.player_id
        )


class ProjectionRow(BaseModel):
    """One element of the UNOFFICIAL `api.sleeper.com/projections/nfl/<season>/<week>`."""

    player_id: str
    season: int
    week: int
    stats: dict[str, float | None] = {}

    @property
    def pts_ppr(self) -> float:
        return float(self.stats.get("pts_ppr") or 0.0)

    @property
    def pts_half_ppr(self) -> float:
        return float(self.stats.get("pts_half_ppr") or 0.0)

    @property
    def pts_std(self) -> float:
        return float(self.stats.get("pts_std") or 0.0)
