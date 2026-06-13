import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import get_client_any_auth, get_current_client, hash_key, hash_password
from dashboard_api.database import get_db

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])


@router.get("", response_model=list[schemas.ClientOut])
def list_clients(db: Session = Depends(get_db), current=Depends(get_client_any_auth)):
    """Return the authenticated client's own info. API keys are not returned."""
    return [current]


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, db: Session = Depends(get_db), current=Depends(get_client_any_auth)):
    """Delete a client and all their data. Only the client themselves can delete their account."""
    if current.id != client_id:
        raise HTTPException(status_code=403, detail="You can only delete your own account")
    # Order matters: TestResult references runs.id, so delete it before Run.
    db.query(models.TestResult).filter(models.TestResult.client_id == client_id).delete()
    db.query(models.Run).filter(models.Run.client_id == client_id).delete()
    db.query(models.Schedule).filter(models.Schedule.client_id == client_id).delete()
    db.query(models.ConnectionConfig).filter(models.ConnectionConfig.client_id == client_id).delete()
    db.query(models.TestDefinition).filter(models.TestDefinition.client_id == client_id).delete()
    db.delete(current)
    db.commit()


@router.post("", response_model=schemas.ClientOut, status_code=201)
def create_client(body: schemas.ClientCreate, db: Session = Depends(get_db)):
    """
    Register a new client. Returns the API key once — store it securely,
    it cannot be retrieved again. Optionally accepts email + password for frontend login.
    """
    if db.query(models.Client).filter(models.Client.name == body.name).first():
        raise HTTPException(status_code=409, detail=f"Client '{body.name}' already exists")

    if body.email and db.query(models.Client).filter(models.Client.email == body.email).first():
        raise HTTPException(status_code=409, detail=f"Email '{body.email}' already registered")

    raw_key = secrets.token_urlsafe(32)
    client = models.Client(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password) if body.password else None,
        api_key_hash=hash_key(raw_key),
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    return schemas.ClientOut(
        id=client.id,
        name=client.name,
        email=client.email,
        created_at=client.created_at,
        api_key=raw_key,  # Only time this is ever returned
    )
