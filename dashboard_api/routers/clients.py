import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import hash_key
from dashboard_api.database import get_db

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])


@router.post("", response_model=schemas.ClientOut, status_code=201)
def create_client(body: schemas.ClientCreate, db: Session = Depends(get_db)):
    """
    Register a new client. Returns the API key once — store it securely,
    it cannot be retrieved again.
    """
    if db.query(models.Client).filter(models.Client.name == body.name).first():
        raise HTTPException(status_code=409, detail=f"Client '{body.name}' already exists")

    raw_key = secrets.token_urlsafe(32)
    client = models.Client(name=body.name, api_key_hash=hash_key(raw_key))
    db.add(client)
    db.commit()
    db.refresh(client)

    return schemas.ClientOut(
        id=client.id,
        name=client.name,
        created_at=client.created_at,
        api_key=raw_key,  # Only time this is ever returned
    )
