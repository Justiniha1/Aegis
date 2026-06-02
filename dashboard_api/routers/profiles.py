from fastapi import APIRouter, Depends

from dashboard_api import models, schemas
from dashboard_api.auth import get_client_any_auth
from dashboard_api import profile_loader

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.get("", response_model=list[schemas.ProfileOut])
def list_profiles(client: models.Client = Depends(get_client_any_auth)):
    """List connection profile NAMES from the connection YAML (names only — never secrets)."""
    names, default = profile_loader.load_profile_names()
    return [schemas.ProfileOut(name=n, is_default=(n == default)) for n in names]
