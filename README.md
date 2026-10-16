# Fantasy Magic

[![CI](https://github.com/NoahSimon2006/FantasyFootball-Magic/actions/workflows/ci.yml/badge.svg)](https://github.com/NoahSimon2006/FantasyFootball-Magic/actions/workflows/ci.yml)

Redraft fantasy football trade values, built from real trades.

Fantasy Magic studies trades that actually happened in public Sleeper leagues to estimate what each player is worth. Those values power a trade calculator ("am I getting value?"), a trending page (who's rising and falling), and trade targets for your own Sleeper roster.

**Status:** early development, working end to end. The data pipeline, value model v0, API and website exist; value model v1 (learned from real trades) and the AI trade advisor are next. See the [roadmap](#roadmap).

## How values work today (v0)

A player's value is how many more fantasy points he is projected to score over the rest of the season than a replacement-level player in your league format (teams, PPR, superflex). Replacement level comes from simulating every team's lineup against one shared player pool, so superflex raises quarterback values for the right reason. A trade's verdict sums each side's values with a discount for extra pieces, and every adjustment is returned as a visible "driver" rather than hidden in a total.

v0 uses projections only. The next version replaces its hand-picked adjustments with values learned from the trades the crawler collects, and is backtested against v0.

## Stack

| Layer | Tech |
| --- | --- |
| Database | PostgreSQL 18 (Docker) |
| API and data pipeline | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, uv |
| Website | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Quality | pytest, mypy (strict), ruff · Vitest, Testing Library, ESLint, Prettier · GitHub Actions CI |

## API

Interactive docs at `/docs` when the API is running. The website calls it through TypeScript types generated from the API's OpenAPI schema, and a test fails if they drift apart.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/values` | Players ranked by value for a league format |
| `POST /api/v1/trades/evaluate` | Who wins a trade, by how much, and why |
| `GET /api/v1/trending` | Most-traded players, plus risers and fallers in value |
| `GET /api/v1/players?q=` | Find players by name |
| `GET /api/v1/health` | Liveness check |

## Run it locally

Prerequisites: [Docker Desktop](https://www.docker.com/products/docker-desktop/), [uv](https://docs.astral.sh/uv/), and Node.js 24.

```bash
# 1. Database (Postgres on 127.0.0.1:5432)
docker compose up -d --wait

# 2. API: http://127.0.0.1:8000/docs
cd api
uv sync
uv run alembic upgrade head
uv run fastapi dev app/main.py

# 3. Website: http://localhost:3000 (in a second terminal)
cd web
npm install
npm run dev
```

### Load data from Sleeper

The website shows "no data yet" states until you load some. From `api/`:

```bash
uv run python -m app.ingest players       # NFL players (one ~15 MB download per day at most)
uv run python -m app.ingest projections   # weekly projections, snapshotted under today's date

# Crawl public leagues outward from a few Sleeper usernames, then collect their trades.
# Both commands stop at a request budget and resume where they left off.
SLEEPER_SEED_USERNAMES=some_username uv run python -m app.ingest seed
uv run python -m app.ingest crawl --max-requests 1500
uv run python -m app.ingest trades --max-requests 3000
uv run python -m app.ingest stats         # row counts, plus a check that "redraft" leagues behave like redraft
```

Settings can also live in `api/.env` (copy `api/example.env`); it is never committed.

## Checks

```bash
cd api && uv run pytest -q && uv run mypy app && uv run ruff check
cd web && npm test && npm run typecheck && npm run lint
```

The API tests run against a real Postgres (a separate `fantasy_magic_test` database, created and migrated automatically, with every test rolled back). CI runs the same checks on every push.

## Roadmap

- [x] Skeleton: Postgres in Docker, FastAPI with migrations, Next.js site, tests and CI
- [x] Data: rate-limited Sleeper client, league crawler, trade and projection ingest
- [x] Value model v0 (projections over replacement) with trade calculator, rankings, and trending endpoints
- [ ] Website: trade calculator, rankings, and trending pages
- [ ] Trade targets from your own Sleeper roster (lineup-aware verdicts)
- [ ] Value model v1 learned from real trades, backtested against v0, with evidence and uncertainty shown for every value
- [ ] AI trade advisor, with an evaluation suite that scores its answers

## Data

Player, league, and trade data comes from the [Sleeper API](https://docs.sleeper.com/), which is free for non-commercial use. Fantasy Magic is a non-commercial project and is not affiliated with Sleeper. Only Sleeper ids, league settings, and trade contents are stored; no usernames, display names, avatars, or league names.
