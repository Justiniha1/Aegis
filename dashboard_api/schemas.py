from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

Status = Literal["PASSED", "FAILED", "ERROR", "SKIPPED"]
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# ── Inbound — what the backend engine sends ──────────────────────────────────

class TestResultIn(BaseModel):
    test_id: str
    name: str
    type: str
    status: Status
    severity: Severity
    metrics: dict
    message: str


class ResultsBatch(BaseModel):
    results: list[TestResultIn]
    run_timestamp: Optional[str] = None


# ── Outbound — what the dashboard reads back ─────────────────────────────────

class TestResultOut(BaseModel):
    id: int
    client_id: int
    test_id: str
    test_name: str
    test_type: str
    status: str
    severity: str
    metrics: dict
    message: str
    run_at: datetime

    model_config = {"from_attributes": True}


# ── Clients ───────────────────────────────────────────────────────────────────

class ClientCreate(BaseModel):
    name: str
    email: Optional[str] = None
    password: Optional[str] = None


class ClientOut(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    created_at: datetime
    api_key: Optional[str] = None  # Only populated on creation; never stored plain

    model_config = {"from_attributes": True}


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    client_id: int
    client_name: str


# ── Test Definitions ──────────────────────────────────────────────────────────

class TestDefinitionIn(BaseModel):
    name: str
    description: Optional[str] = None
    type: str
    severity: Severity = "MEDIUM"
    enabled: bool = True
    tags: list[str] = []
    config: dict                   # type-specific fields: table, column, threshold, etc.
    profile: str = "dev"


class TestDefinitionOut(BaseModel):
    id: int
    client_id: int
    name: str
    description: Optional[str]
    type: str
    severity: str
    enabled: bool
    tags: list
    config: dict
    profile: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class YamlImport(BaseModel):
    yaml_content: str              # raw YAML string pasted or uploaded by the user
