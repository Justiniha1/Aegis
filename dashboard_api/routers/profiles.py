from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import get_client_any_auth
from dashboard_api.database import get_db
from dashboard_api.encryption import encrypt

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])

# Fields copied straight from create/update bodies onto the model row.
_STRUCT_FIELDS = ("db_type", "host", "port", "database", "username", "sqlite_path", "secret_env")


def _default_secret_env(name: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in name).upper()
    return f"AEGIS_{safe}_PASSWORD"


@router.post("", response_model=schemas.ConnectionProfileOut, status_code=201)
def upsert_profile(
    body: schemas.ConnectionProfileCreate,
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    """Create or update a profile by (client_id, name). Upsert so `aegis push` is idempotent.

    Secret handling (no-clobber): if secret_value is provided it is encrypted and stored;
    if omitted, any existing secret is preserved.
    """
    row = db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.client_id == client.id,
        models.ConnectionProfile.name == body.name,
    ).first()

    is_new = row is None
    if is_new:
        row = models.ConnectionProfile(client_id=client.id, name=body.name)

    for f in _STRUCT_FIELDS:
        setattr(row, f, getattr(body, f))

    # Secretless dbs (sqlite) carry no secret_env.
    if (row.db_type or "").lower() == "sqlite":
        row.secret_env = None
    elif row.secret_env is None:
        row.secret_env = _default_secret_env(body.name)

    # No-clobber: only write a secret when a non-empty one is supplied. An empty
    # string (e.g. an unset env var flowing through the CLI) means "keep existing".
    if body.secret_value:
        row.secret_encrypted = encrypt(body.secret_value)

    if is_new:
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[schemas.ConnectionProfileOut])
def list_profiles(
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    return db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.client_id == client.id
    ).order_by(models.ConnectionProfile.name.asc()).all()


@router.put("/{profile_id}", response_model=schemas.ConnectionProfileOut)
def update_profile(
    profile_id: int,
    body: schemas.ConnectionProfileUpdate,
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    row = db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.id == profile_id,
        models.ConnectionProfile.client_id == client.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")

    for f in _STRUCT_FIELDS:
        val = getattr(body, f)
        if val is not None:
            setattr(row, f, val)

    if (row.db_type or "").lower() == "sqlite":
        row.secret_env = None

    if body.secret_value:                      # no-clobber: empty/None preserves existing
        row.secret_encrypted = encrypt(body.secret_value)

    db.commit()
    db.refresh(row)
    return row


@router.delete("/{profile_id}", status_code=204)
def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    row = db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.id == profile_id,
        models.ConnectionProfile.client_id == client.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(row)
    db.commit()
    return Response(status_code=204)
