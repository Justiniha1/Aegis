from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import verify_password, create_access_token
from dashboard_api.database import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    """
    Exchange email + password for a JWT token.
    The token is valid for 24 hours and should be sent as: Authorization: Bearer <token>
    """
    client = db.query(models.Client).filter(models.Client.email == body.email).first()
    if not client or not client.password_hash or not verify_password(body.password, client.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return schemas.TokenOut(
        access_token=create_access_token(client.id),
        client_id=client.id,
        client_name=client.name,
    )
