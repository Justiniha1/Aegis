from datetime import datetime
from typing import Optional

from pydantic import BaseModel


 
# Inbound — what the backend engine sends
class TestResultIn(BaseModel):
    test_id: str
    name: str
    type: str
    status: str
    severity: str
    metrics: dict
    message: str


class ResultsBatch(BaseModel):
    results: list[TestResultIn]
    run_timestamp: Optional[str] = None


# Outbound — what the dashboard reads back 
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


class ClientCreate(BaseModel):
    name: str


class ClientOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    api_key: Optional[str] = None  # Only populated on creation; never stored plain

    model_config = {"from_attributes": True}
