from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
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


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    test_id = Column(String, nullable=False)
    test_name = Column(String, nullable=False)
    test_type = Column(String, nullable=False)
    status = Column(String, nullable=False)       # PASSED / FAILED / ERROR / SKIPPED
    severity = Column(String, nullable=False)     # LOW / MEDIUM / HIGH / CRITICAL
    metrics = Column(JSON)
    message = Column(String)
    run_at = Column(DateTime, nullable=False)

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
