"""Database tables for Sleeper data.

Data minimization: we store Sleeper *ids* needed to crawl and to value trades, never
usernames, display names, avatars, or league names of other people.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Player(Base):
    """NFL players from Sleeper's daily `/players/nfl` dump (fantasy positions only)."""

    __tablename__ = "players"

    player_id: Mapped[str] = mapped_column(primary_key=True)
    full_name: Mapped[str]
    position: Mapped[str | None]
    team: Mapped[str | None]
    age: Mapped[int | None]
    years_exp: Mapped[int | None]
    status: Mapped[str | None]
    injury_status: Mapped[str | None]
    updated_at: Mapped[datetime]


class ProjectionSnapshot(Base):
    """Weekly projected points as fetched on `snapshot_date`.

    Append-only by date: re-fetching on the same day overwrites that day's row, but never
    an earlier day's, so "projection movers" can compare today against last week.
    """

    __tablename__ = "projection_snapshots"

    snapshot_date: Mapped[date] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(primary_key=True)
    week: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[str] = mapped_column(primary_key=True)
    pts_ppr: Mapped[float]
    pts_half_ppr: Mapped[float]
    pts_std: Mapped[float]


class CrawlUser(Base):
    """A Sleeper user id in the crawl frontier. Only the id is stored."""

    __tablename__ = "crawl_users"

    user_id: Mapped[str] = mapped_column(primary_key=True)
    discovered_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # NULL = still waiting in the frontier; set once this user's leagues were fetched.
    leagues_fetched_at: Mapped[datetime | None]


class League(Base):
    """A Sleeper league and the settings that decide which value format it belongs to."""

    __tablename__ = "leagues"
    __table_args__ = (Index("ix_leagues_season_type", "season", "league_type"),)

    league_id: Mapped[str] = mapped_column(primary_key=True)
    season: Mapped[int]
    status: Mapped[str]
    # Sleeper settings.type: 0 = redraft (validated by the crawler), 1 keeper, 2 dynasty.
    league_type: Mapped[int | None]
    total_rosters: Mapped[int]
    ppr: Mapped[float]  # points per reception: 0, 0.5, 1
    is_superflex: Mapped[bool]
    trade_deadline: Mapped[int | None]
    previous_league_id: Mapped[str | None]
    discovered_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Crawl progress: NULL = not done yet. Lets every job resume where it stopped.
    members_fetched_at: Mapped[datetime | None]
    trades_fetched_through_week: Mapped[int] = mapped_column(default=0, server_default="0")
    trades_fetched_at: Mapped[datetime | None]

    # Mirrors the trades.league_id FK's ON DELETE CASCADE. With the default cascade, deleting
    # a league made the ORM set each trade's league_id to NULL first, which the NOT NULL
    # column rejects; passive_deletes leaves unloaded trades to the database's cascade.
    trades: Mapped[list["Trade"]] = relationship(
        back_populates="league", cascade="all, delete-orphan", passive_deletes=True
    )


class Trade(Base):
    """A completed trade. `raw` keeps Sleeper's full payload so we can re-derive assets."""

    __tablename__ = "trades"

    transaction_id: Mapped[str] = mapped_column(primary_key=True)
    league_id: Mapped[str] = mapped_column(
        ForeignKey("leagues.league_id", ondelete="CASCADE"), index=True
    )
    season: Mapped[int]
    week: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(index=True)
    roster_ids: Mapped[list[int]] = mapped_column(JSONB)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(server_default=func.now())

    league: Mapped[League] = relationship(back_populates="trades")
    assets: Mapped[list["TradeAsset"]] = relationship(
        back_populates="trade", cascade="all, delete-orphan", passive_deletes=True
    )


class TradeAsset(Base):
    """One thing that changed hands in a trade: a player, a draft pick, or FAAB dollars."""

    __tablename__ = "trade_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("trades.transaction_id", ondelete="CASCADE"), index=True
    )
    asset_type: Mapped[str]  # "player" | "pick" | "faab"
    from_roster_id: Mapped[int | None]
    to_roster_id: Mapped[int]
    player_id: Mapped[str | None] = mapped_column(index=True)
    pick_season: Mapped[int | None]
    pick_round: Mapped[int | None]
    faab_amount: Mapped[int | None]

    trade: Mapped[Trade] = relationship(back_populates="assets")
