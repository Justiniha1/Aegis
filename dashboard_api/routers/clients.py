import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import (
    get_client_any_auth,
    get_current_client,
    get_current_client_jwt,
    hash_key,
    hash_password,
)
from dashboard_api.database import get_db
from dashboard_api.runtime_checks import is_production

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])


def require_admin(x_admin_token: str = Header(None)):
    """Gate client provisioning behind an operator admin token.

    The token is required whenever COMET_ADMIN_TOKEN is configured, and always in
    production (so the endpoint is never publicly open where it is exposed). In local
    development with no token set, provisioning stays open for `make seed`.
    """
    expected = os.getenv("COMET_ADMIN_TOKEN", "")
    if is_production() or expected:
        if not expected or not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
            raise HTTPException(status_code=403, detail="Admin token required to create clients")


@router.get("", response_model=list[schemas.ClientOut])
def list_clients(db: Session = Depends(get_db), current=Depends(get_client_any_auth)):
    """Return the authenticated client's own info. API keys are not returned."""
    return [current]


@router.patch("/me", response_model=schemas.ClientOut)
def update_me(
    body: schemas.ClientUpdate,
    db: Session = Depends(get_db),
    client=Depends(get_current_client_jwt),
):
    """Update the authenticated client's own settings (e.g. the failure-alert webhook).

    Pass an empty string for alert_webhook_url to clear it.
    """
    if body.alert_webhook_url is not None:
        client.alert_webhook_url = body.alert_webhook_url or None
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, db: Session = Depends(get_db), current=Depends(get_client_any_auth)):
    """Delete a client and all their test results. Only the client themselves can delete their account."""
    if current.id != client_id:
        raise HTTPException(status_code=403, detail="You can only delete your own account")
    db.query(models.TestResult).filter(models.TestResult.client_id == client_id).delete()
    db.query(models.TestDefinition).filter(models.TestDefinition.client_id == client_id).delete()
    db.delete(current)
    db.commit()


@router.post("", response_model=schemas.ClientOut, status_code=201)
def create_client(
    body: schemas.ClientCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """
    Register a new client. Returns the API key once — store it securely,
    it cannot be retrieved again. Optionally accepts email + password for frontend login.

    Requires the X-Admin-Token header when COMET_ADMIN_TOKEN is configured (always in
    production); open in local development for `make seed`.
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
