from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (and `api/.env` if present).

    Field names map to env vars case-insensitively: `database_url` <- `DATABASE_URL`.
    Defaults point at the local Docker Postgres from `docker-compose.yml`, so the app
    runs with no `.env` at all during development.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 127.0.0.1, not "localhost": on Windows "localhost" tries IPv6 (::1) first, where
    # Docker isn't listening, and psycopg then waits on that dead attempt. connect_timeout
    # turns any unreachable database into a clear error after 10s instead of a silent hang.
    database_url: str = (
        "postgresql+psycopg://fantasy:fantasy@127.0.0.1:5432/fantasy_magic?connect_timeout=10"
    )

    # Comma-separated Sleeper usernames the league crawler starts from.
    sleeper_seed_usernames: str = ""
    # Ceiling on Sleeper API calls. Sleeper asks clients to stay under 1000/minute.
    sleeper_max_requests_per_minute: int = 600
    # Local cache directory (gitignored), e.g. for the daily ~15 MB /players/nfl download.
    cache_dir: Path = Path(".cache")

    @property
    def seed_usernames(self) -> list[str]:
        """`SLEEPER_SEED_USERNAMES` split on commas, with blanks dropped."""
        return [name.strip() for name in self.sleeper_seed_usernames.split(",") if name.strip()]


@lru_cache
def get_settings() -> Settings:
    """Build Settings once and reuse it; tests can call `get_settings.cache_clear()`."""
    return Settings()
