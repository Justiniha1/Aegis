from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

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
    run_id: Optional[int] = None    # Phase 2 — set by UI-triggered runs via execute_run
    run_profile: Optional[str] = None  # used when auto-creating a Run for make run path


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
    run_id: Optional[int] = None
    # Enriched from TestDefinition.config at query time (not stored in TestResult)
    table: Optional[str] = None
    column: Optional[str] = None

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
    alert_webhook_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ClientUpdate(BaseModel):
    # Self-service settings a client may change. Use "" to clear the webhook.
    alert_webhook_url: Optional[str] = None


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


# ── Runs (Phase 2) ────────────────────────────────────────────────────────────

RunStatus = Literal["QUEUED", "RUNNING", "COMPLETE", "FAILED"]


class RunCreate(BaseModel):
    profile: str = Field(..., max_length=128)
    type_filter: Optional[list[str]] = None   # None = "all enabled tests"


class RunErrorDetail(BaseModel):
    reason: str
    at_test: Optional[int] = None


class RunOut(BaseModel):
    id: int
    client_id: int
    profile: str
    type_filter: Optional[list[str]] = None
    status: RunStatus
    total_tests: int
    completed_tests: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[RunErrorDetail] = None     # composed from error_reason + error_at_test

    model_config = {"from_attributes": False}  # composed manually in the router — see 02-02


class RunTriggerOut(BaseModel):
    run_id: int
    total_tests: int
    status: RunStatus


# ── Profiles (Phase 2) ────────────────────────────────────────────────────────

class ProfileOut(BaseModel):
    name: str
    is_default: bool = False
    db_type: str = ""
    website_schedulable: bool = False


# ── Schedules (Phase 9) ───────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    profile: str = Field(..., max_length=128)
    preset: Literal["hourly", "daily", "weekly"]
    at_hour: int = Field(0, ge=0, le=23)
    at_minute: int = Field(0, ge=0, le=59)
    weekday: int = Field(0, ge=0, le=6)
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    preset: Optional[Literal["hourly", "daily", "weekly"]] = None
    at_hour: Optional[int] = Field(None, ge=0, le=23)
    at_minute: Optional[int] = Field(None, ge=0, le=59)
    weekday: Optional[int] = Field(None, ge=0, le=6)


class ScheduleOut(BaseModel):
    id: int
    client_id: int
    profile: str
    preset: Optional[str] = None
    cron: Optional[str] = None
    enabled: bool
    last_run_at: Optional[datetime] = None
    next_run_at: datetime

    model_config = {"from_attributes": True}

