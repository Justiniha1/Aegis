from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dashboard_api import models, schemas, connection_source
from dashboard_api.auth import get_client_any_auth
from dashboard_api.database import get_db

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.get("", response_model=list[schemas.ProfileOut])
def list_profiles(
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    """List connection profile NAMES (never secrets) from the uploaded or on-disk YAML.

    Each profile also carries db_type (unresolved YAML type label) and website_schedulable
    (derived from db_type via the shared predicate — no ${ENV} resolution, no secrets).
    """
    yaml_text = connection_source.get_yaml_text(db, client.id)
    names, default = connection_source.profile_names(yaml_text)
    types = connection_source.profile_types(yaml_text)
    return [
        schemas.ProfileOut(
            name=n,
            is_default=(n == default),
            db_type=types.get(n, ""),
            website_schedulable=connection_source.is_website_schedulable(types.get(n, "")),
        )
        for n in names
    ]


@router.post("/sync")
def sync_profiles(
    body: schemas.YamlImport,
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    """Upload the local database_connection.yaml. Stored per client; preferred over the on-disk file."""
    row = (
        db.query(models.ConnectionConfig)
        .filter(models.ConnectionConfig.client_id == client.id)
        .first()
    )
    if row is None:
        row = models.ConnectionConfig(client_id=client.id, yaml_text=body.yaml_content)
        db.add(row)
    else:
        row.yaml_text = body.yaml_content
        row.updated_at = datetime.utcnow()
    db.commit()
    names, _ = connection_source.profile_names(body.yaml_content)
    return {"ok": True, "profiles": names}
