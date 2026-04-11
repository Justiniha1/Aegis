import re

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import get_client_any_auth, get_current_client_jwt
from dashboard_api.database import get_db

router = APIRouter(prefix="/api/v1/tests", tags=["tests"])


def _name_to_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


@router.get("", response_model=list[schemas.TestDefinitionOut])
def list_tests(
    client=Depends(get_client_any_auth),
    db: Session = Depends(get_db),
):
    """
    List all test definitions for this client.
    Accepts API key (engine) or JWT (frontend).
    """
    return (
        db.query(models.TestDefinition)
        .filter(models.TestDefinition.client_id == client.id)
        .order_by(models.TestDefinition.created_at.asc())
        .all()
    )


@router.post("", response_model=schemas.TestDefinitionOut, status_code=201)
def create_test(
    body: schemas.TestDefinitionIn,
    client=Depends(get_current_client_jwt),
    db: Session = Depends(get_db),
):
    test = models.TestDefinition(client_id=client.id, **body.model_dump())
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@router.put("/{test_id}", response_model=schemas.TestDefinitionOut)
def update_test(
    test_id: int,
    body: schemas.TestDefinitionIn,
    client=Depends(get_current_client_jwt),
    db: Session = Depends(get_db),
):
    test = (
        db.query(models.TestDefinition)
        .filter(
            models.TestDefinition.id == test_id,
            models.TestDefinition.client_id == client.id,
        )
        .first()
    )
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    for key, value in body.model_dump().items():
        setattr(test, key, value)

    from datetime import datetime
    test.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(test)
    return test


@router.delete("/{test_id}", status_code=204)
def delete_test(
    test_id: int,
    client=Depends(get_current_client_jwt),
    db: Session = Depends(get_db),
):
    test = (
        db.query(models.TestDefinition)
        .filter(
            models.TestDefinition.id == test_id,
            models.TestDefinition.client_id == client.id,
        )
        .first()
    )
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    db.delete(test)
    db.commit()


@router.post("/import", status_code=201)
def import_from_yaml(
    body: schemas.YamlImport,
    client=Depends(get_current_client_jwt),
    db: Session = Depends(get_db),
):
    """
    Import test definitions from a YAML string.
    Expects the same format as test_definitions.yaml.
    Returns counts of imported and skipped tests.
    """
    try:
        raw = yaml.safe_load(body.yaml_content) or {}
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {e}")

    raw_tests = raw.get("tests", [])
    if not raw_tests:
        raise HTTPException(status_code=422, detail="No tests found under 'tests:' key")

    settings = raw.get("settings", {})
    default_profile = settings.get("default_profile", "dev")
    default_severity = settings.get("default_severity", "MEDIUM")

    imported, skipped = 0, 0
    for t in raw_tests:
        if not t.get("enabled", True):
            skipped += 1
            continue

        # Separate standard fields from type-specific config
        standard_keys = {"name", "description", "type", "severity", "enabled", "tags", "profile"}
        config = {k: v for k, v in t.items() if k not in standard_keys}

        test = models.TestDefinition(
            client_id=client.id,
            name=t["name"],
            description=t.get("description"),
            type=t["type"],
            severity=t.get("severity", default_severity),
            enabled=True,
            tags=t.get("tags", []),
            config=config,
            profile=t.get("profile", default_profile),
        )
        db.add(test)
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped}
