from fastapi import APIRouter, Depends

from dashboard_api import schemas
from dashboard_api.auth import get_current_client_jwt
from dashboard_api.profile_loader import load_profile_names

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.get("", response_model=list[schemas.ProfileOut])
def list_profiles(
    _client=Depends(get_current_client_jwt),
):
    """Return profile NAMES from database_connection.yaml.

    Per Phase 2 security_constraints: names only — never connection strings,
    hosts, ports, or credentials. JWT-only (frontend dropdown is the sole caller).
    The `_client` dependency exists to enforce authentication; the response
    does NOT vary by client (profile YAML is engine-tier config, not per-tenant).
    """
    names, default = load_profile_names()
    return [
        schemas.ProfileOut(name=n, is_default=(n == default))
        for n in names
    ]
