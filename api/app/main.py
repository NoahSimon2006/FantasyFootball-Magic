from fastapi import FastAPI

from app.errors import register_error_handlers
from app.routers import health, methodology, players, trades, trending, values

app = FastAPI(
    title="Fantasy Magic API",
    version="0.1.0",
    description="Redraft fantasy football trade values built from real Sleeper trades.",
)

register_error_handlers(app)

for router in (
    health.router,
    players.router,
    values.router,
    trades.router,
    trending.router,
    methodology.router,
):
    app.include_router(router, prefix="/api/v1")
