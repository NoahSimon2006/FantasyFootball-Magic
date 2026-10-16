"""Small builders for putting known data into the test database.

Each function adds rows to the given session and flushes (never commits; the `db_session`
fixture rolls everything back after the test).
"""

from collections.abc import Mapping
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.db.models import League, Player, ProjectionSnapshot, Trade, TradeAsset

SEASON = 2026


def add_players(session: Session, positions: Mapping[str, str]) -> None:
    """One Player per `player_id: position`, named "Player <id>"."""
    now = datetime(2026, 10, 15, tzinfo=UTC)
    for player_id, position in positions.items():
        session.add(
            Player(
                player_id=player_id,
                full_name=f"Player {player_id}",
                position=position,
                team="DEN",
                status="Active",
                updated_at=now,
            )
        )
    session.flush()


def add_league(session: Session, league_id: str, *, league_type: int = 0) -> None:
    session.add(
        League(
            league_id=league_id,
            season=SEASON,
            status="in_season",
            league_type=league_type,
            total_rosters=12,
            ppr=1.0,
            is_superflex=False,
        )
    )
    session.flush()


def add_trade(
    session: Session,
    transaction_id: str,
    league_id: str,
    created_at: datetime,
    *,
    players: tuple[str, ...] = (),
    picks: int = 0,
) -> None:
    """A trade that sent each of `players` from roster 1 to roster 2, plus `picks` draft picks."""
    session.add(
        Trade(
            transaction_id=transaction_id,
            league_id=league_id,
            season=SEASON,
            week=6,
            created_at=created_at,
            roster_ids=[1, 2],
            raw={},
        )
    )
    session.flush()
    for player_id in players:
        session.add(
            TradeAsset(
                transaction_id=transaction_id,
                asset_type="player",
                from_roster_id=1,
                to_roster_id=2,
                player_id=player_id,
            )
        )
    for _ in range(picks):
        session.add(
            TradeAsset(
                transaction_id=transaction_id,
                asset_type="pick",
                from_roster_id=1,
                to_roster_id=2,
                pick_season=SEASON + 1,
                pick_round=1,
            )
        )
    session.flush()


def add_snapshot(
    session: Session, day: date, weekly_points: Mapping[str, float], weeks: tuple[int, ...]
) -> None:
    """A projection snapshot taken on `day`: each player scores `points` in each of `weeks`.

    Reception-free numbers (std = half = full PPR) keep hand calculations simple.
    """
    for player_id, points in weekly_points.items():
        for week in weeks:
            session.add(
                ProjectionSnapshot(
                    snapshot_date=day,
                    season=SEASON,
                    week=week,
                    player_id=player_id,
                    pts_ppr=points,
                    pts_half_ppr=points,
                    pts_std=points,
                )
            )
    session.flush()
