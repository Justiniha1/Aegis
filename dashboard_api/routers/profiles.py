from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import get_client_any_auth
from dashboard_api.database import get_db
from dashboard_api.encryption import encrypt

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.post("", response_model=schemas.ConnectionProfileOut, status_code=201)
def create_profile(
    body: schemas.ConnectionProfileCreate,
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    existing = db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.client_id == client.id,
        models.ConnectionProfile.name == body.name,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Profile '{body.name}' already exists")
    profile = models.ConnectionProfile(
        client_id=client.id,
        name=body.name,
        connection_url_encrypted=encrypt(body.connection_url),
        db_type=body.db_type,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("", response_model=list[schemas.ConnectionProfileOut])
def list_profiles(
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    return db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.client_id == client.id
    ).all()


@router.delete("/{profile_id}", status_code=204)
def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    profile = db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.id == profile_id,
        models.ConnectionProfile.client_id == client.id,
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(profile)
    db.commit()
    return Response(status_code=204)
