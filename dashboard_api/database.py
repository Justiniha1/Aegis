import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dashboard.db")

# check_same_thread is SQLite-only; Postgres doesn't need it
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_active_run_index() -> None:
    """Idempotently create the 'one active run per client' partial unique index.

    create_all() adds this index from the model definition for fresh databases, but it
    does not alter an already-existing 'runs' table (e.g. the production Postgres). This
    issues an IF NOT EXISTS partial-index DDL — valid on both SQLite and Postgres — so the
    constraint also lands on pre-existing deployments. A pre-existing duplicate active run
    would make creation fail; we log and continue rather than block startup.
    """
    ddl = text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_runs_one_active_per_client "
        "ON runs (client_id) WHERE status IN ('QUEUED', 'RUNNING')"
    )
    try:
        with engine.begin() as conn:
            conn.execute(ddl)
    except Exception as e:  # pragma: no cover - defensive (legacy duplicate active runs)
        logging.getLogger(__name__).warning(
            "Could not create uq_runs_one_active_per_client index "
            "(existing duplicate active runs?): %s", e
        )


def ensure_client_alert_column() -> None:
    """Idempotently add clients.alert_webhook_url to an existing database.

    create_all() adds it for fresh databases via the model; this covers the already
    provisioned production 'clients' table. No-op when the column already exists.
    """
    from sqlalchemy import inspect as _inspect

    try:
        existing = {c["name"] for c in _inspect(engine).get_columns("clients")}
    except Exception:  # pragma: no cover - table not present yet
        return
    if "alert_webhook_url" in existing:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE clients ADD COLUMN alert_webhook_url VARCHAR"))
    except Exception as e:  # pragma: no cover - defensive
        logging.getLogger(__name__).warning(
            "Could not add clients.alert_webhook_url column: %s", e
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
