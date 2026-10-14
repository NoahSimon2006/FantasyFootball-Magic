from fastapi import FastAPI

from app.routers import health

app = FastAPI(
    title="Fantasy Magic API",
    version="0.1.0",
    description="Redraft fantasy football trade values built from real Sleeper trades.",
)

app.include_router(health.router, prefix="/api/v1")
