from types import MappingProxyType

import pytest

from app.valuation.formats import STANDARD_SUPERFLEX, LeagueFormat


def test_default_format_is_sleepers_standard_12_team_ppr_1qb() -> None:
    fmt = LeagueFormat()

    assert (fmt.teams, fmt.ppr, fmt.is_superflex) == (12, 1.0, False)
    assert dict(fmt.slots) == {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1}


def test_standard_superflex_adds_one_super_flex_slot() -> None:
    assert STANDARD_SUPERFLEX.is_superflex
    assert STANDARD_SUPERFLEX.slots["SUPER_FLEX"] == 1


def test_from_roster_positions_counts_starting_slots_and_ignores_the_rest() -> None:
    sleeper_positions = [
        "QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "K", "DEF", "BN", "BN", "IR",
    ]  # fmt: skip

    fmt = LeagueFormat.from_roster_positions(sleeper_positions, teams=10, ppr=0.5)

    assert dict(fmt.slots) == {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "SUPER_FLEX": 1}
    assert (fmt.teams, fmt.ppr, fmt.is_superflex) == (10, 0.5, True)


def test_unknown_slot_code_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown slot codes"):
        LeagueFormat(slots=MappingProxyType({"QB": 1, "WIZARD": 1}))


def test_a_league_needs_at_least_one_team() -> None:
    with pytest.raises(ValueError, match="teams must be at least 1"):
        LeagueFormat(teams=0)
