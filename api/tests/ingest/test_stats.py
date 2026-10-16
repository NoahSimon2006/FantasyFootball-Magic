"""collect_stats / format_stats on a small hand-built dataset whose answers are worked out
by hand in `dataset` below.

Every row is written through `db_session`, so it is rolled back when the test ends.
"""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from app.db.models import CrawlUser, League, Player, ProjectionSnapshot, Trade, TradeAsset
from app.ingest.stats import (
    IngestStats,
    LeagueGroup,
    LeagueTypeTrades,
    collect_stats,
    format_stats,
)

FETCHED_AT = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def make_league(
    league_id: str,
    *,
    season: int = 2026,
    league_type: int | None = 0,
    members_fetched: bool = False,
    trades_fetched: bool = False,
) -> League:
    return League(
        league_id=league_id,
        season=season,
        status="in_season",
        league_type=league_type,
        total_rosters=12,
        ppr=1.0,
        is_superflex=False,
        members_fetched_at=FETCHED_AT if members_fetched else None,
        trades_fetched_at=FETCHED_AT if trades_fetched else None,
    )


def make_trade(transaction_id: str, league: League, *assets: TradeAsset) -> Trade:
    """A trade in `league`, made during the league's own season."""
    return Trade(
        transaction_id=transaction_id,
        league=league,
        season=league.season,
        week=5,
        created_at=datetime(league.season, 10, 5, tzinfo=UTC),
        roster_ids=[1, 2],
        raw={"type": "trade", "status": "complete"},
        assets=list(assets),
    )


def player(player_id: str) -> TradeAsset:
    return TradeAsset(asset_type="player", player_id=player_id, from_roster_id=1, to_roster_id=2)


def pick(season: int, pick_round: int = 1) -> TradeAsset:
    return TradeAsset(
        asset_type="pick",
        pick_season=season,
        pick_round=pick_round,
        from_roster_id=2,
        to_roster_id=1,
    )


def faab(amount: int) -> TradeAsset:
    return TradeAsset(asset_type="faab", faab_amount=amount, from_roster_id=2, to_roster_id=1)


def make_player(player_id: str) -> Player:
    return Player(player_id=player_id, full_name=f"Test Player {player_id}", updated_at=FETCHED_AT)


def make_snapshot(snapshot_date: date, player_id: str) -> ProjectionSnapshot:
    return ProjectionSnapshot(
        snapshot_date=snapshot_date,
        season=2026,
        week=6,
        player_id=player_id,
        pts_ppr=12.0,
        pts_half_ppr=10.5,
        pts_std=9.0,
    )


@pytest.fixture
def dataset(db_session: Session) -> Session:
    """The hand-built dataset. Expected answers:

    - 3 players; 3 projection rows, latest on 2026-10-15
    - 4 crawl users, 3 of them still waiting (leagues_fetched_at NULL)
    - leagues (season, type): (2026, 0) x2 with 1 member list and 1 trade fetch done;
      (2026, 2) x1 fully fetched; (2026, unset) x1 untouched; (2025, 0) x1 fully fetched
    - trades: 6 in 2026, 2 in 2025
    - type 0: 4 trades; 1 has a pick (a 2026 pick traded in 2026: not a future pick)
    - type 2: 4 trades; 2 have a pick; 1 has future picks (two of them, counted once)
    - assets: 8 player, 4 pick, 2 faab rows
    """
    redraft_2026 = make_league("r26-a", members_fetched=True, trades_fetched=True)
    redraft_2026_new = make_league("r26-b")
    redraft_2025 = make_league("r25", season=2025, members_fetched=True, trades_fetched=True)
    dynasty_2026 = make_league("d26", league_type=2, members_fetched=True, trades_fetched=True)
    unknown_type = make_league("u26", league_type=None)
    db_session.add_all(
        [
            make_player("1"),
            make_player("2"),
            make_player("3"),
            make_snapshot(date(2026, 10, 14), "1"),
            make_snapshot(date(2026, 10, 14), "2"),
            make_snapshot(date(2026, 10, 15), "1"),
            CrawlUser(user_id="u1", leagues_fetched_at=FETCHED_AT),
            CrawlUser(user_id="u2"),
            CrawlUser(user_id="u3"),
            CrawlUser(user_id="u4"),
            redraft_2026_new,
            unknown_type,
            # Type 0 (believed redraft)
            make_trade("r1", redraft_2026, player("10"), player("11")),
            make_trade("r2", redraft_2026, player("12"), pick(2026, 5)),
            make_trade("r3", redraft_2025, player("13"), faab(10)),
            make_trade("r4", redraft_2025, player("14"), player("15")),
            # Type 2 (believed dynasty)
            make_trade("d1", dynasty_2026, pick(2027, 1), pick(2028, 2)),
            make_trade("d2", dynasty_2026, player("16"), faab(5)),
            make_trade("d3", dynasty_2026, pick(2026, 3)),
            make_trade("d4", dynasty_2026, player("17")),
        ]
    )
    db_session.flush()
    return db_session


@pytest.fixture
def stats(dataset: Session) -> IngestStats:
    return collect_stats(dataset)


def test_counts_players(stats: IngestStats) -> None:
    assert stats.players == 3


def test_counts_projection_rows_and_finds_the_latest_snapshot_date(stats: IngestStats) -> None:
    assert (stats.projection_snapshots, stats.latest_snapshot_date) == (3, date(2026, 10, 15))


def test_counts_crawl_users_and_those_still_waiting_in_the_frontier(stats: IngestStats) -> None:
    assert (stats.crawl_users, stats.crawl_users_waiting) == (4, 3)


def test_groups_leagues_by_season_and_type_with_crawl_progress(stats: IngestStats) -> None:
    assert stats.leagues == (
        LeagueGroup(season=2026, league_type=0, leagues=2, members_fetched=1, trades_fetched=1),
        LeagueGroup(season=2026, league_type=2, leagues=1, members_fetched=1, trades_fetched=1),
        LeagueGroup(season=2026, league_type=None, leagues=1, members_fetched=0, trades_fetched=0),
        LeagueGroup(season=2025, league_type=0, leagues=1, members_fetched=1, trades_fetched=1),
    )


def test_counts_trades_by_season(stats: IngestStats) -> None:
    assert stats.trades_by_season == {2026: 6, 2025: 2}


def test_counts_trade_assets_by_type(stats: IngestStats) -> None:
    assert stats.trade_assets_by_type == {"faab": 2, "pick": 4, "player": 8}


def test_counts_trades_with_picks_and_future_picks_by_league_type(stats: IngestStats) -> None:
    assert stats.trades_by_league_type == (
        LeagueTypeTrades(league_type=0, trades=4, with_pick=1, with_future_pick=0),
        LeagueTypeTrades(league_type=2, trades=4, with_pick=2, with_future_pick=1),
    )


def test_validation_shares_are_fractions_of_each_types_trades(stats: IngestStats) -> None:
    shares = [(row.pick_share, row.future_pick_share) for row in stats.trades_by_league_type]

    assert shares == [(0.25, 0.0), (0.5, 0.25)]


def test_future_pick_is_judged_against_the_trades_own_season(db_session: Session) -> None:
    league = make_league("d25", season=2025, league_type=2)
    db_session.add_all(
        [
            make_trade("t-next-season", league, pick(2026)),  # 2026 > 2025: future
            make_trade("t-same-season", league, pick(2025)),  # same season: not future
        ]
    )
    db_session.flush()

    [row] = collect_stats(db_session).trades_by_league_type

    assert row.with_future_pick == 1


def test_shares_of_a_type_without_trades_are_zero() -> None:
    row = LeagueTypeTrades(league_type=1, trades=0, with_pick=0, with_future_pick=0)

    assert (row.pick_share, row.future_pick_share) == (0.0, 0.0)


def test_empty_database_gives_zero_counts_and_no_latest_snapshot(db_session: Session) -> None:
    assert collect_stats(db_session) == IngestStats(
        players=0,
        projection_snapshots=0,
        latest_snapshot_date=None,
        crawl_users=0,
        crawl_users_waiting=0,
        leagues=(),
        trades_by_season={},
        trades_by_league_type=(),
        trade_assets_by_type={},
    )


def test_report_shows_each_types_validation_shares_as_percentages(stats: IngestStats) -> None:
    rows = [line.split() for line in format_stats(stats).splitlines()]

    # type, trades, share with a pick, share with a future pick
    assert ["0", "4", "25.0%", "0.0%"] in rows and ["2", "4", "50.0%", "25.0%"] in rows


def test_report_lists_leagues_newest_season_first(stats: IngestStats) -> None:
    rows = [line.split() for line in format_stats(stats).splitlines()]
    league_rows = [row for row in rows if len(row) == 5 and row[0] in {"2025", "2026"}]

    # season, type, leagues, members fetched, trades fetched
    assert league_rows == [
        ["2026", "0", "2", "1", "1"],
        ["2026", "2", "1", "1", "1"],
        ["2026", "unset", "1", "0", "0"],
        ["2025", "0", "1", "1", "1"],
    ]


def test_report_says_when_only_one_league_type_has_trades(db_session: Session) -> None:
    # What the report shows while only redraft leagues have had their trades fetched.
    db_session.add(make_trade("t1", make_league("r26"), player("10")))
    db_session.flush()

    assert "nothing to compare yet" in format_stats(collect_stats(db_session))


def test_report_with_two_league_types_has_no_nothing_to_compare_note(stats: IngestStats) -> None:
    assert "nothing to compare yet" not in format_stats(stats)


def test_report_on_an_empty_database_marks_every_table_as_empty(db_session: Session) -> None:
    report = format_stats(collect_stats(db_session))

    assert report.count("(none yet)") == 4 and "latest snapshot: none yet" in report
