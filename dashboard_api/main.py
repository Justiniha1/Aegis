import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dashboard_api import models
from dashboard_api.database import engine
from dashboard_api.routers import auth_routes, clients, profiles, results, runs, tests

# Create all tables on startup (no-op if they already exist)
models.Base.metadata.create_all(bind=engine)

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
)

# Allow the Next.js frontend to call the API
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


@app.get("/api/v1/health", tags=["health"])
def health():
    return {"status": "ok"}
