"""Row counts and a sanity check over everything ingest has stored.

`collect_stats` reads the database; `format_stats` turns the result into plain-text tables
for the terminal (`uv run python -m app.ingest stats`).

The last table checks a guess the value model depends on. Sleeper doesn't document a
league's `settings.type`; we believe 0 = redraft, 1 = keeper, 2 = dynasty. Dynasty managers
trade future draft picks all the time, while a redraft league has no future draft to trade
picks in. So if the guess is right, many type 2 trades include a pick for a later season and
almost no type 0 trades do.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CrawlUser, League, Player, ProjectionSnapshot, Trade, TradeAsset


@dataclass(frozen=True)
class LeagueGroup:
    """The leagues of one season and league type, and how far the crawl has got with them."""

    season: int
    league_type: int | None
    leagues: int
    members_fetched: int  # leagues whose member list has been fetched
    trades_fetched: int  # leagues whose trades have been fetched at least once


@dataclass(frozen=True)
class LeagueTypeTrades:
    """The trades in leagues of one type, and how many of them include draft picks."""

    league_type: int | None
    trades: int
    with_pick: int  # trades with at least one draft pick
    with_future_pick: int  # trades with a pick for a season after the trade's own season

    @property
    def pick_share(self) -> float:
        return self.with_pick / self.trades if self.trades else 0.0

    @property
    def future_pick_share(self) -> float:
        return self.with_future_pick / self.trades if self.trades else 0.0


@dataclass(frozen=True)
class IngestStats:
    players: int
    projection_snapshots: int  # rows, across every snapshot date
    latest_snapshot_date: date | None  # None until projections have been ingested
    crawl_users: int
    crawl_users_waiting: int  # leagues not fetched yet: still waiting in the crawl frontier
    leagues: tuple[LeagueGroup, ...]  # newest season first
    trades_by_season: Mapping[int, int]  # newest season first
    trades_by_league_type: tuple[LeagueTypeTrades, ...]  # the league-type validation table
    trade_assets_by_type: Mapping[str, int]  # asset_type -> rows


def collect_stats(session: Session) -> IngestStats:
    """Count what ingest has stored. Read-only."""
    players = session.execute(select(func.count()).select_from(Player)).scalar_one()

    projection_snapshots, latest_snapshot_date = session.execute(
        select(func.count(), func.max(ProjectionSnapshot.snapshot_date)).select_from(
            ProjectionSnapshot
        )
    ).one()

    crawl_users, crawl_users_waiting = session.execute(
        select(
            func.count(), func.count().filter(CrawlUser.leagues_fetched_at.is_(None))
        ).select_from(CrawlUser)
    ).one()

    # Each query selects its columns in the order of the dataclass fields it fills.
    # count(column) counts only the rows where that column is not NULL.
    leagues = tuple(
        LeagueGroup(*row)
        for row in session.execute(
            select(
                League.season,
                League.league_type,
                func.count(),
                func.count(League.members_fetched_at),
                func.count(League.trades_fetched_at),
            )
            .group_by(League.season, League.league_type)
            .order_by(League.season.desc(), League.league_type.asc().nulls_last())
        )
    )

    trades_by_season = dict(
        session.execute(
            select(Trade.season, func.count()).group_by(Trade.season).order_by(Trade.season.desc())
        ).all()
    )

    # EXISTS per trade, so a trade with three picks still counts once.
    pick_in_trade = (
        select(TradeAsset.id)
        .where(TradeAsset.transaction_id == Trade.transaction_id, TradeAsset.asset_type == "pick")
        .correlate(Trade)
    )
    future_pick_in_trade = pick_in_trade.where(TradeAsset.pick_season > Trade.season)
    trades_by_league_type = tuple(
        LeagueTypeTrades(*row)
        for row in session.execute(
            select(
                League.league_type,
                func.count(),
                func.count().filter(pick_in_trade.exists()),
                func.count().filter(future_pick_in_trade.exists()),
            )
            .select_from(Trade)
            .join(Trade.league)
            .group_by(League.league_type)
            .order_by(League.league_type.asc().nulls_last())
        )
    )

    trade_assets_by_type = dict(
        session.execute(
            select(TradeAsset.asset_type, func.count())
            .group_by(TradeAsset.asset_type)
            .order_by(TradeAsset.asset_type)
        ).all()
    )

    return IngestStats(
        players=players,
        projection_snapshots=projection_snapshots,
        latest_snapshot_date=latest_snapshot_date,
        crawl_users=crawl_users,
        crawl_users_waiting=crawl_users_waiting,
        leagues=leagues,
        trades_by_season=trades_by_season,
        trades_by_league_type=trades_by_league_type,
        trade_assets_by_type=trade_assets_by_type,
    )


def format_stats(stats: IngestStats) -> str:
    """The stats as plain-text tables, ready to print."""
    latest = stats.latest_snapshot_date.isoformat() if stats.latest_snapshot_date else "none yet"
    totals = "\n".join(
        [
            f"{'Players':<22}{stats.players:>12,}",
            f"{'Projection rows':<22}{stats.projection_snapshots:>12,}  latest snapshot: {latest}",
            f"{'Crawl users':<22}{stats.crawl_users:>12,}  "
            f"waiting in the frontier: {stats.crawl_users_waiting:,}",
        ]
    )
    leagues = _section(
        "Leagues by season and type",
        ["season", "type", "leagues", "members fetched", "trades fetched"],
        [
            [
                str(group.season),
                _type_label(group.league_type),
                f"{group.leagues:,}",
                f"{group.members_fetched:,}",
                f"{group.trades_fetched:,}",
            ]
            for group in stats.leagues
        ],
    )
    trades_by_season = _section(
        "Trades by season",
        ["season", "trades"],
        [[str(season), f"{count:,}"] for season, count in stats.trades_by_season.items()],
    )
    assets = _section(
        "Trade assets by type",
        ["asset type", "rows"],
        [[asset_type, f"{count:,}"] for asset_type, count in stats.trade_assets_by_type.items()],
        align="lr",
    )
    validation = _section(
        "Trades by league type (a check on what Sleeper's undocumented settings.type means)\n"
        "We believe 0 = redraft, 1 = keeper, 2 = dynasty. If so, type 2 trades often include a\n"
        "future pick (one for a later season than the trade's) and type 0 trades almost never.",
        ["type", "trades", "with a pick", "with a future pick"],
        [
            [
                _type_label(row.league_type),
                f"{row.trades:,}",
                f"{row.pick_share:.1%}",
                f"{row.future_pick_share:.1%}",
            ]
            for row in stats.trades_by_league_type
        ],
    )
    if len(stats.trades_by_league_type) == 1:
        # A single row can't confirm or refute anything, and shouldn't be misread as a pass.
        validation += "\n  Only one league type has trades so far: nothing to compare yet."
    return "\n\n".join([totals, leagues, trades_by_season, assets, validation])


def _type_label(league_type: int | None) -> str:
    return "unset" if league_type is None else str(league_type)


def _section(
    title: str, headers: Sequence[str], rows: Sequence[Sequence[str]], *, align: str = ""
) -> str:
    """A title over an indented table. `align` has an "l" or "r" per column (default: all "r")."""
    if not rows:
        return f"{title}\n  (none yet)"
    sides = align or "r" * len(headers)
    widths = [max(len(cell) for cell in column) for column in zip(headers, *rows, strict=True)]

    def line(cells: Sequence[str]) -> str:
        padded = (
            cell.ljust(width) if side == "l" else cell.rjust(width)
            for cell, width, side in zip(cells, widths, sides, strict=True)
        )
        return "  " + "  ".join(padded).rstrip()

    return "\n".join([title, line(headers), *(line(row) for row in rows)])
