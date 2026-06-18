"""Production configuration guardrails.

These prevent the API from booting in a production deployment with settings that
silently lose or compromise client data:
- an insecure/placeholder JWT signing secret (forgeable logins; logout-on-redeploy), or
- a non-persistent database (SQLite on Railway is wiped on every redeploy).

The checks are gated on COMET_ENV=production, so local development and the test suite
(which default to "development") are unaffected.
"""

import os

# JWT secrets that are unsafe to ship — empty or the documented placeholder.
PLACEHOLDER_JWT_SECRETS = {"", "change-me-in-production"}


def is_production(env: dict | None = None) -> bool:
    env = env if env is not None else os.environ
    return env.get("COMET_ENV", "development").lower() == "production"


def check_production_config(env: dict | None = None) -> list[str]:
    """Return a list of fatal production-config problems, or [] if the config is safe.

    In non-production environments this always returns [] (the guardrails are inert).
    """
    env = env if env is not None else os.environ
    if not is_production(env):
        return []

    problems: list[str] = []

    if env.get("JWT_SECRET_KEY", "") in PLACEHOLDER_JWT_SECRETS:
        problems.append(
            "JWT_SECRET_KEY must be set to a strong, persistent secret in production "
            "(it is currently unset or the default placeholder). Generate one with "
            "`python -c \"import secrets; print(secrets.token_hex(32))\"` and set it on "
            "the API service."
        )

    db_url = env.get("DATABASE_URL", "")
    if not db_url or db_url.startswith("sqlite"):
        problems.append(
            "DATABASE_URL must point at a persistent database (e.g. managed Postgres) in "
            "production. SQLite lives on the container's ephemeral disk and loses all "
            "client data on every redeploy. On Railway set DATABASE_URL to "
            "${{Postgres.DATABASE_URL}}."
        )

    if not env.get("COMET_ADMIN_TOKEN", ""):
        problems.append(
            "COMET_ADMIN_TOKEN must be set in production. It gates client provisioning "
            "(POST /api/v1/clients) so accounts are created only by the operator, never "
            "by the public."
        )

    return problems
