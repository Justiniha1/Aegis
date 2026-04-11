from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from dashboard_api.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    api_key_hash = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    results = relationship("TestResult", back_populates="client")


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
