import hashlib

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from dashboard_api import models
from dashboard_api.database import get_db


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def get_current_client(
    x_api_key: str = Header(..., description="Client API key"),
    db: Session = Depends(get_db),
):
    key_hash = hash_key(x_api_key)
    client = (
        db.query(models.Client)
        .filter(models.Client.api_key_hash == key_hash)
        .first()
    )
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return client
