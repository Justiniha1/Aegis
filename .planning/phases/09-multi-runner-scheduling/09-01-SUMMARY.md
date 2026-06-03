---
phase: 09-multi-runner-scheduling
plan: "01"
subsystem: backend-connector
tags: [snowflake, drivers, dialect, loud-fail, credentials, optional-extras]
dependency_graph:
  requires: []
  provides: [snowflake-dialect, env-loud-fail, per-db-extras, hosted-drivers]
  affects: [backend/core/database_connector.py, dashboard_api/requirements.txt, pyproject.toml, cli/commands/init.py, cli/templates/database_connection.yaml]
tech_stack:
  added: [snowflake-sqlalchemy==1.10.0, PyMySQL==1.2.0, tzdata]
  patterns: [per-DB optional extras in pyproject.toml, ENV loud-fail in build_connection_url, account-locator normalization]
key_files:
  created: [tests/test_aegis_dq/test_build_connection_url.py]
  modified:
    - backend/core/database_connector.py
    - dashboard_api/requirements.txt
    - pyproject.toml
    - cli/commands/init.py
    - cli/templates/database_connection.yaml
decisions:
  - "Snowflake auth via password ${ENV} reference; key-pair deferred per locked decision"
  - "all-db extra excludes pyodbc (MSSQL is client-lane-only; DB-03)"
  - "Loud-fail pre-check placed before connection_url short-circuit so it catches all paths"
  - "Credential scrubbing: error messages name only the ENV variable, never its value"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-02"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 5
---

# Phase 9 Plan 01: Driver & Dialect Coverage Summary

**One-liner:** Snowflake dialect in build_connection_url with account normalization, warehouse/role query params, unset-${ENV} loud-fail, credential scrubbing, hosted pinned drivers, per-DB optional extras, and Snowflake ${ENV} example in aegis init + YAML template.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Snowflake branch + unset-ENV loud-fail (TDD) | 646e37f | backend/core/database_connector.py, tests/test_aegis_dq/test_build_connection_url.py |
| 2 | Hosted cloud drivers + per-DB optional extras | ae5128f | dashboard_api/requirements.txt, pyproject.toml |
| 3 | Snowflake ${ENV} template in aegis init + YAML docs | 1144688 | cli/commands/init.py, cli/templates/database_connection.yaml |

## Implementation Details

### Task 1: build_connection_url extensions

Added `_ENV_VAR_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")` and a pre-check loop that
iterates all string values in the profile dict before any URL construction. Any literal
`${VAR}` value raises `ValueError` naming only the variable name — never the value itself.
This satisfies T-09A-01 (no credential leakage) and T-09A-02 (no literal-string-to-connector).

The Snowflake branch:
- Strips `.snowflakecomputing.com` suffix from account if present
- Builds warehouse/role as optional query params (no dangling `?` or `&` when absent)
- Returns `snowflake://user:pass@account/database[?warehouse=W[&role=R]]`

The Unsupported-type error no longer names any profile field values (only the db_type string,
which came from the type field — not a credential).

### Task 2: requirements + extras

`dashboard_api/requirements.txt` pins `PyMySQL==1.2.0`, `snowflake-sqlalchemy==1.10.0`,
and `tzdata` (needed by the Wave C scheduler for timezone resolution on python:3.13-slim).

`pyproject.toml` adds five new optional extras mirroring the existing `airflow` shape:
`postgres`, `mysql`, `snowflake`, `mssql`, `all-db`. The `all-db` extra deliberately omits
`pyodbc` because it requires system ODBC libs and MSSQL is client-lane-only (DB-03).

### Task 3: Templates

Both `cli/commands/init.py` (inline `_DATABASE_CONNECTION_YAML`) and
`cli/templates/database_connection.yaml` gain a commented Snowflake profile block using
`${SNOWFLAKE_USER}` / `${SNOWFLAKE_PASSWORD}` and the org-account locator format (no
`.snowflakecomputing.com` suffix). The YAML template header also documents the Snowflake
SQLAlchemy URL format.

## Verification Results

- `pytest tests/test_aegis_dq/test_build_connection_url.py -q`: 7 passed
- `pytest tests/ -q`: 42 passed, 9 warnings (no regressions; was 35 before this plan)
- `grep "snowflake://" backend/core/database_connector.py`: hit found
- tomllib confirms five optional extras exist; all-db excludes pyodbc
- Hosted requirements pin snowflake-sqlalchemy==1.10.0, PyMySQL==1.2.0, tzdata

## TDD Gate Compliance

- RED gate: tests written before implementation; 7 tests failed as expected
- GREEN gate: implementation added; all 7 tests passed
- REFACTOR: not needed — code was clean on first pass

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The only new trust
boundary is the pre-check in `build_connection_url` which is a mitigation (T-09A-02), not
new attack surface.

## Self-Check: PASSED

- backend/core/database_connector.py: modified, contains "snowflake://"
- tests/test_aegis_dq/test_build_connection_url.py: created, 7 tests
- dashboard_api/requirements.txt: contains snowflake-sqlalchemy==1.10.0, PyMySQL==1.2.0, tzdata
- pyproject.toml: contains snowflake, mysql, mssql, postgres, all-db extras
- cli/commands/init.py: contains "type: snowflake" and "SNOWFLAKE_PASSWORD"
- cli/templates/database_connection.yaml: contains "snowflake"
- Commits 646e37f, ae5128f, 1144688: all present in git log
