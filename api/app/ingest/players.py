"""Load Sleeper's NFL player dump into the `players` table.

The dump is Sleeper's full player list (about 15 MB). The client caches it on disk for a
day, because Sleeper asks for at most one download per day. Only the positions a redraft
league can roster are kept.
"""

import logging
from datetime import datetime
from itertools import batched

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Player
from app.sleeper.client import SleeperClient
from app.sleeper.models import SleeperPlayer

logger = logging.getLogger(__name__)

# What a QB/RB/WR/TE/K/DEF league can roster. The dump also lists offensive linemen,
# defensive players (IDP), and so on, which no trade in such a league can include.
FANTASY_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "K", "DEF"})

# Rows per INSERT. Each row binds 9 parameters, so a statement stays far below Postgres's
# limit of 65,535 parameters, and no single statement grows unboundedly large.
ROWS_PER_STATEMENT = 1000


def ingest_players(session: Session, client: SleeperClient, *, now: datetime) -> int:
    """Upsert every player at a fantasy position; return the number of rows written.

    An upsert inserts a player we haven't seen and overwrites one we have. It's keyed on
    Sleeper's `player_id`, so running this twice leaves the same rows: a player who changed
    teams gets the new team, and nobody is duplicated. `updated_at` is set to `now` on every
    row written, so it records when the row was last refreshed from Sleeper.

    Players are filtered on their primary `position`. A player whose primary position is
    something else is skipped, even if his `fantasy_positions` would let him fill one of
    these slots.

    The caller owns the transaction: nothing here commits.
    """
    players = client.get_players()
    rows = [
        _row(player, now) for player in players.values() if player.position in FANTASY_POSITIONS
    ]
    # strict=False: the last batch is allowed to be shorter than the others.
    for batch in batched(rows, ROWS_PER_STATEMENT, strict=False):
        statement = insert(Player).values(list(batch))
        # On a player_id that already exists, overwrite every column we sent (all but the key).
        overwrite = {
            column: statement.excluded[column] for column in batch[0] if column != "player_id"
        }
        session.execute(
            statement.on_conflict_do_update(index_elements=["player_id"], set_=overwrite)
        )
    logger.info(
        "Upserted %d players; skipped %d at other positions", len(rows), len(players) - len(rows)
    )
    return len(rows)


def _row(player: SleeperPlayer, now: datetime) -> dict[str, object]:
    """One `players` row. Team defenses have no `full_name`; `display_name` covers them."""
    return {
        "player_id": player.player_id,
        "full_name": player.display_name,
        "position": player.position,
        "team": player.team,
        "age": player.age,
        "years_exp": player.years_exp,
        "status": player.status,
        "injury_status": player.injury_status,
        "updated_at": now,
    }
