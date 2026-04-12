import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from dashboard_api import models
from dashboard_api.database import get_db

# ── API key auth (used by the backend engine) ─────────────────────────────────

def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def get_current_client(
    x_api_key: str = Header(..., description="Client API key"),
    db: Session = Depends(get_db),
):
    """Authenticate via API key header. Used by the backend engine."""
    key_hash = hash_key(x_api_key)
    client = (
        db.query(models.Client)
        .filter(models.Client.api_key_hash == key_hash)
        .first()
    )
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return client


# ── JWT auth (used by the frontend) ──────────────────────────────────────────

_SECRET = os.getenv("JWT_SECRET_KEY", "")
if not _SECRET:
    import secrets as _s
    _SECRET = _s.token_hex(32)
    import warnings
    warnings.warn("JWT_SECRET_KEY not set — using random key (tokens won't survive restarts)", stacklevel=1)
_ALGORITHM = "HS256"
_EXPIRE_HOURS = 24

bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(client_id: int) -> str:
    expire = datetime.utcnow() + timedelta(hours=_EXPIRE_HOURS)
    return jwt.encode({"sub": str(client_id), "exp": expire}, _SECRET, algorithm=_ALGORITHM)


def get_current_client_jwt(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Authenticate via JWT Bearer token. Used by the frontend."""
    try:
        payload = jwt.decode(credentials.credentials, _SECRET, algorithms=[_ALGORITHM])
        client_id = int(payload["sub"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=401, detail="Client not found")
    return client


def get_client_any_auth(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Accept either API key or JWT. Used by endpoints called by both engine and frontend."""
    if x_api_key:
        key_hash = hash_key(x_api_key)
        client = db.query(models.Client).filter(models.Client.api_key_hash == key_hash).first()
        if client:
            return client

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
            client_id = int(payload["sub"])
            client = db.query(models.Client).filter(models.Client.id == client_id).first()
            if client:
                return client
        except jwt.PyJWTError:
            pass

    raise HTTPException(status_code=401, detail="Authentication required")
