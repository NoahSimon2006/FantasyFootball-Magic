# Fantasy Magic

Redraft fantasy football trade values, built from real trades.

Fantasy Magic studies trades that actually happened in public Sleeper leagues to estimate what each player is worth. Those values power a trade calculator ("am I getting value?"), a trending page (who's rising and falling), and trade targets for your own Sleeper roster.

**Status:** early development. The skeleton runs end to end (database, API, website, tests); the Sleeper data pipeline is next. See the [roadmap](#roadmap).

## Stack

| Layer | Tech |
| --- | --- |
| Database | PostgreSQL 18 (Docker) |
| API and data pipeline | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, uv |
| Website | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Quality | pytest, mypy (strict), ruff · Vitest, Testing Library, ESLint, Prettier |

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

## Checks

```bash
cd api && uv run pytest -q && uv run mypy app && uv run ruff check
cd web && npm test && npm run typecheck && npm run lint
```

## Roadmap

- [x] Skeleton: Postgres in Docker, FastAPI with migrations, Next.js site, tests on both sides
- [ ] Data: Sleeper API client, league crawler, trade and projection ingest
- [ ] MVP: trade calculator, trending players, trade targets from your Sleeper roster
- [ ] Trade-market value model, backtested against a projections-only baseline
- [ ] AI trade advisor, with an evaluation suite that scores its answers

## Data

Player, league, and trade data comes from the [Sleeper API](https://docs.sleeper.com/), which is free for non-commercial use. Fantasy Magic is a non-commercial project and is not affiliated with Sleeper.
