"""Sprint Planner API: teams, sprints, user stories, burndown and velocity."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import settings
from .database import Base, engine
from .routers import auth, sprints, stories, teams


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # For a production system you'd run migrations (e.g. Alembic) instead.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Sprint Planner API",
    version=__version__,
    description="Plan Scrum sprints as a team: backlog, capacity, burndown and velocity forecasting.",
    lifespan=lifespan,
)

# Allow browser front ends (e.g. sprint-dashboard) on the listed origins to call the API.
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

for r in (auth.router, teams.router, sprints.router, stories.router):
    app.include_router(r)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
