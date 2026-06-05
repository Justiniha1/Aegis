from datetime import datetime

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import get_client_any_auth, get_current_client_jwt
from dashboard_api.database import get_db
from fastapi.responses import PlainTextResponse
from dashboard_api.yaml_sync import export_tests_to_yaml, generate_yaml_string, _STANDARD_KEYS

router = APIRouter(prefix="/api/v1/tests", tags=["tests"])


@router.get("/yaml", response_class=PlainTextResponse)
def get_yaml(
    client=Depends(get_client_any_auth),
    db: Session = Depends(get_db),
):
    """Return the current test definitions as a YAML string for the editor."""
    return generate_yaml_string(db, client.id)


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
    export_tests_to_yaml(db, client.id)
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

    test.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(test)
    export_tests_to_yaml(db, client.id)
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
    export_tests_to_yaml(db, client.id)


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

    # Get existing test names so we don't create duplicates
    existing_names = set(
        name for (name,) in db.query(models.TestDefinition.name)
        .filter(models.TestDefinition.client_id == client.id)
        .all()
    )

    imported, skipped = 0, 0
    for t in raw_tests:
        if not t.get("enabled", True):
            skipped += 1
            continue

        if t["name"] in existing_names:
            skipped += 1
            continue

        config = {k: v for k, v in t.items() if k not in _STANDARD_KEYS}

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
    export_tests_to_yaml(db, client.id)
    return {"imported": imported, "skipped": skipped}


@router.post("/sync", status_code=200)
def sync_from_yaml(
    body: schemas.YamlImport,
    client=Depends(get_client_any_auth),
    db: Session = Depends(get_db),
):
    """
    Sync test definitions from a YAML string to the database.
    Matches tests by name: creates new, updates changed, deletes removed.
    Called by the engine on startup to push manual YAML edits to the DB.
    """
    try:
        raw = yaml.safe_load(body.yaml_content) or {}
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {e}")

    raw_tests = raw.get("tests", [])
    settings = raw.get("settings", {})
    default_profile = settings.get("default_profile", "dev")
    default_severity = settings.get("default_severity", "MEDIUM")

    # Get existing DB tests for this client, indexed by name
    existing = (
        db.query(models.TestDefinition)
        .filter(models.TestDefinition.client_id == client.id)
        .all()
    )
    db_by_name = {t.name: t for t in existing}

    # Track which names are in the YAML
    yaml_names = set()
    created, updated, unchanged = 0, 0, 0

    for t in raw_tests:
        name = t.get("name", "")
        if not name:
            continue
        yaml_names.add(name)

        config = {k: v for k, v in t.items() if k not in _STANDARD_KEYS}
        severity = t.get("severity", default_severity)
        profile = t.get("profile", default_profile)
        enabled = t.get("enabled", True)
        tags = t.get("tags", [])
        description = t.get("description")
        test_type = t.get("type", "")

        if name in db_by_name:
            # Check if anything changed
            db_test = db_by_name[name]
            changed = (
                db_test.type != test_type
                or db_test.severity != severity
                or db_test.profile != profile
                or db_test.enabled != enabled
                or db_test.tags != tags
                or db_test.description != description
                or db_test.config != config
            )
            if changed:
                db_test.type = test_type
                db_test.severity = severity
                db_test.profile = profile
                db_test.enabled = enabled
                db_test.tags = tags
                db_test.description = description
                db_test.config = config
                db_test.updated_at = datetime.utcnow()
                updated += 1
            else:
                unchanged += 1
        else:
            # New test from YAML
            db.add(models.TestDefinition(
                client_id=client.id,
                name=name,
                description=description,
                type=test_type,
                severity=severity,
                enabled=enabled,
                tags=tags,
                config=config,
                profile=profile,
            ))
            created += 1

    # Delete tests that are in DB but not in YAML
    deleted = 0
    for name, db_test in db_by_name.items():
        if name not in yaml_names:
            db.delete(db_test)
            deleted += 1

    db.commit()
    # Re-export to ensure YAML matches DB exactly (e.g., default values filled in)
    export_tests_to_yaml(db, client.id)
    return {"created": created, "updated": updated, "deleted": deleted, "unchanged": unchanged}
