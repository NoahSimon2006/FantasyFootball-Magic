"""League formats: which starting slots each team fills, and how receptions score.

Values are only meaningful relative to a format. A QB is worth far more when every team
can start two of them (superflex), and a pass-catching RB gains value in full PPR.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

# Positions v0 values. Kickers and defenses aren't modeled (they're rarely traded, and our
# projections ingest only covers QB/RB/WR/TE), so they always come out at value 0.
VALUED_POSITIONS = ("QB", "RB", "WR", "TE")

# Sleeper's starting-slot codes and the positions each can hold. Slots not listed here
# (K, DEF, BN bench, IR, IDP slots) don't affect QB/RB/WR/TE replacement levels.
SLOT_ELIGIBILITY: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "QB": ("QB",),
        "RB": ("RB",),
        "WR": ("WR",),
        "TE": ("TE",),
        "WRRB_FLEX": ("RB", "WR"),
        "REC_FLEX": ("WR", "TE"),
        "FLEX": ("RB", "WR", "TE"),
        "SUPER_FLEX": ("QB", "RB", "WR", "TE"),
    }
)


def _default_slots() -> Mapping[str, int]:
    return MappingProxyType({"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1})


@dataclass(frozen=True)
class LeagueFormat:
    """Everything about a league that changes player values.

    `slots` counts starting slots PER TEAM by Sleeper slot code (see SLOT_ELIGIBILITY).
    The default is Sleeper's standard 12-team, full-PPR, 1QB lineup.
    """

    teams: int = 12
    ppr: float = 1.0
    slots: Mapping[str, int] = field(default_factory=_default_slots)

    def __post_init__(self) -> None:
        if self.teams < 1:
            raise ValueError(f"teams must be at least 1, got {self.teams}")
        unknown = sorted(set(self.slots) - set(SLOT_ELIGIBILITY))
        if unknown:
            raise ValueError(f"unknown slot codes: {unknown}")

    @property
    def is_superflex(self) -> bool:
        return self.slots.get("SUPER_FLEX", 0) > 0

    @classmethod
    def from_roster_positions(
        cls, roster_positions: Sequence[str], *, teams: int, ppr: float
    ) -> "LeagueFormat":
        """Build a format from a Sleeper league's `roster_positions` list.

        Slots we don't value (K, DEF, bench, IDP) are ignored rather than rejected, so any
        real Sleeper league can be described.
        """
        counts: dict[str, int] = {}
        for slot in roster_positions:
            if slot in SLOT_ELIGIBILITY:
                counts[slot] = counts.get(slot, 0) + 1
        return cls(teams=teams, ppr=ppr, slots=MappingProxyType(counts))


STANDARD_1QB = LeagueFormat()
STANDARD_SUPERFLEX = LeagueFormat(
    slots=MappingProxyType({"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "SUPER_FLEX": 1})
)
