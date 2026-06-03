import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from dashboard_api.limiter import limiter

from dashboard_api import models
from dashboard_api.database import engine
from dashboard_api.routers import auth_routes, clients, profiles, results, runs, schedules, tests


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: create tables then optionally start the scheduler.

    Single-process requirement: the Dockerfile CMD is already single-process/single-replica.
    AEGIS_SCHEDULER_ENABLED=1 (the default) starts the in-process poller here.
    Set AEGIS_SCHEDULER_ENABLED=0 (or any value other than "1") to disable — this is the
    seam for future graduation to a dedicated worker process or to disable polling in test
    environments that do not want a background thread.
    """
    # Create all tables on startup (no-op if they already exist).
    models.Base.metadata.create_all(bind=engine)

    if os.getenv("AEGIS_SCHEDULER_ENABLED", "1") == "1":
        from dashboard_api.scheduler import start_scheduler
        from dashboard_api.database import SessionLocal
        start_scheduler()
        # Count enabled schedules for the startup log so operators can verify rehydration.
        db = SessionLocal()
        try:
            n = db.query(models.Schedule).filter(models.Schedule.enabled == True).count()  # noqa: E712
        finally:
            db.close()
        print(
            f"[scheduler] enabled — single in-process poller (60s); "
            f"rehydrated {n} enabled schedule(s)"
        )
    else:
        print("[scheduler] disabled (AEGIS_SCHEDULER_ENABLED != 1)")

    yield

    from dashboard_api.scheduler import stop_scheduler
    stop_scheduler()


# CORS: read allowed origins from env var; default to localhost:3000 for local dev.
# Production: set ALLOWED_ORIGINS=https://dashboard.yourdomain.com
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

app = FastAPI(
    title="DQF Dashboard API",
    description="Receives test results from client backend engines and serves them to the dashboard.",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting — per-client quota on run-trigger endpoint
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# SlowAPIMiddleware must be added before CORSMiddleware so that CORS (outermost
# in Starlette's LIFO order) wraps rate-limit responses — otherwise 429s lack
# Access-Control-Allow-Origin headers and the browser sees a CORS error.
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(results.router)
app.include_router(clients.router)
app.include_router(tests.router)
app.include_router(runs.router)
app.include_router(profiles.router)
app.include_router(schedules.router)


@app.get("/api/v1/health", tags=["health"])
def health():
    return {"status": "ok"}
