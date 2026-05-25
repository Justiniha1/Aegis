from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import relationship

from dashboard_api.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=True)
    api_key_hash = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    results = relationship("TestResult", back_populates="client")
    test_definitions = relationship("TestDefinition", back_populates="client", cascade="all, delete-orphan")
    connection_profiles = relationship("ConnectionProfile", cascade="all, delete-orphan")


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

    __table_args__ = (Index("ix_runs_client_started", "client_id", "started_at"),)


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


class ConnectionProfile(Base):
    __tablename__ = "connection_profiles"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String, nullable=False)          # e.g. "production", "dev"
    connection_url_encrypted = Column(String, nullable=False)
    db_type = Column(String, nullable=False)       # display only: "postgresql", "mysql", etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_profiles_client_name", "client_id", "name", unique=True),
    )
