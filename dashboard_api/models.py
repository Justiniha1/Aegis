from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship

from dashboard_api.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=True)
    api_key_hash = Column(String, unique=True, nullable=False)
    # Optional per-client webhook (Slack/generic) for scheduled-run failure alerts.
    alert_webhook_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    results = relationship("TestResult", back_populates="client")
    test_definitions = relationship("TestDefinition", back_populates="client", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    profile = Column(String, nullable=False)
    type_filter = Column(JSON, nullable=True)        # list[str] of test types, or None for "all"
    status = Column(String, nullable=False, default="QUEUED")   # QUEUED / RUNNING / COMPLETE / FAILED
    total_tests = Column(Integer, nullable=False, default=0)
    completed_tests = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    error_reason = Column(String, nullable=True)     # D-17 specificity contract — populated on FAILED
    error_at_test = Column(Integer, nullable=True)   # 1-indexed test number that errored (D-15)

    __table_args__ = (
        Index("ix_runs_client_started", "client_id", "started_at"),
        # At most one active (QUEUED/RUNNING) run per client — DB-level D-09 guard so a
        # poller/manual-trigger race cannot create two concurrent runs (the check-then-insert
        # in queries.active_run is only advisory). Applied to fresh DBs by create_all and to
        # existing DBs by database.ensure_active_run_index().
        Index(
            "uq_runs_one_active_per_client",
            "client_id",
            unique=True,
            sqlite_where=text("status IN ('QUEUED', 'RUNNING')"),
            postgresql_where=text("status IN ('QUEUED', 'RUNNING')"),
        ),
    )


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    test_id = Column(String, nullable=False)
    test_name = Column(String, nullable=False)
    test_type = Column(String, nullable=False)
    status = Column(String, nullable=False)       # PASSED / FAILED / ERROR / SKIPPED
    severity = Column(String, nullable=False)     # LOW / MEDIUM / HIGH / CRITICAL
    metrics = Column(JSON)
    message = Column(String)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=True, index=True)
    run_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (Index("ix_results_client_run", "client_id", "run_at"),)

    client = relationship("Client", back_populates="results")


class TestDefinition(Base):
    __tablename__ = "test_definitions"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    type = Column(String, nullable=False)
    severity = Column(String, nullable=False, default="MEDIUM")
    enabled = Column(Boolean, default=True, nullable=False)
    tags = Column(JSON, default=list)
    config = Column(JSON, nullable=False)          # type-specific fields: table, column, threshold, etc.
    profile = Column(String, default="dev", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="test_definitions")


class ConnectionConfig(Base):
    __tablename__ = "connection_config"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, unique=True, index=True)
    yaml_text = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.utcnow)


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    profile = Column(String, nullable=False)
    cron = Column(String, nullable=True)              # canonical UTC cron, human-inspectable
    interval_seconds = Column(Integer, nullable=True) # reserved; presets use cron
    preset = Column(String, nullable=True)            # "hourly"|"daily"|"weekly"
    at_hour = Column(Integer, nullable=True)
    at_minute = Column(Integer, nullable=True, default=0)
    weekday = Column(Integer, nullable=True)          # 0=Mon for weekly
    enabled = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_schedules_due", "enabled", "next_run_at"),
        UniqueConstraint("client_id", "profile", name="uq_schedule_client_profile"),
    )
