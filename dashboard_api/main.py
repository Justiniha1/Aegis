from fastapi import FastAPI

from dashboard_api import models
from dashboard_api.database import engine
from dashboard_api.routers import clients, results

# Create all tables on startup (no-op if they already exist)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DQF Dashboard API",
    description="Receives test results from client backend engines and serves them to the dashboard.",
    version="1.0.0",
)

app.include_router(results.router)
app.include_router(clients.router)


@app.get("/api/v1/health", tags=["health"])
def health():
    return {"status": "ok"}
