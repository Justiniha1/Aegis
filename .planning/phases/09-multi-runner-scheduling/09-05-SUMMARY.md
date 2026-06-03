---
phase: 09-multi-runner-scheduling
plan: "05"
subsystem: cli-config-and-docs
tags: [cli, config, optional-config-yaml, client-lane, runbook, deploy, scheduler-caveats, tdd]
dependency_graph:
  requires: [09-02, 09-04]
  provides: [optional-config-yaml, client-lane-runbook, scheduler-deploy-caveats]
  affects:
    - cli/config.py
    - tests/test_cli/test_config.py
    - docs/client-lane.md
    - DEPLOY.md
    - README.md
    - .gitignore
tech_stack:
  added: []
  patterns:
    - optional-file-with-defaults
    - TDD-red-green
key_files:
  created:
    - docs/client-lane.md
  modified:
    - cli/config.py
    - tests/test_cli/test_config.py
    - DEPLOY.md
    - README.md
    - .gitignore
decisions:
  - "config.yaml is now an optional override; api_url defaults to https://api.aegis-dq.com; AEGIS_API_KEY still required"
  - "docs/ exclusion in .gitignore narrowed to docs/superpowers/ so docs/client-lane.md is tracked in the repo"
  - "DEPLOY.md Hosted scheduler section documents single-process invariant, AEGIS_SCHEDULER_ENABLED gate, no-Alembic create_all note, skip-missed behavior, and Snowflake IP allowlist limitation"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-02"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 6
  tests_added: 2
  tests_total: 68
---

# Phase 09 Plan 05: CLI Config Simplification + Client-Lane Docs Summary

Wave D — CLI config simplification and client-lane documentation.

**One-liner:** load_config no longer exits on missing config.yaml (api_url defaults to hosted dashboard, only AEGIS_API_KEY required); client-lane runbook documents self-run + AegisDQOperator scheduling; DEPLOY.md captures single-replica/AEGIS_SCHEDULER_ENABLED/no-Alembic/Snowflake-IP caveats.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for optional config.yaml defaults | cff11da | tests/test_cli/test_config.py |
| 1 (GREEN) | make aegis/config.yaml optional in load_config | 928e1fb | cli/config.py |
| 2 | Client-lane runbook + DEPLOY.md scheduler caveats + README pointer | 76b0aba | docs/client-lane.md, DEPLOY.md, README.md, .gitignore |

## What Was Built

### Task 1: load_config — optional config.yaml (TDD)

**RED:** `tests/test_cli/test_config.py` edited in place:
- `test_load_config_raises_when_no_config_yaml` replaced with `test_load_config_without_file_uses_defaults`: `tmp_path` has no `aegis/` directory, `AEGIS_API_KEY` set in env, `load_dotenv` patched to no-op — asserts `api_url == "https://api.aegis-dq.com"`, `default_profile == "dev"`, `api_key == env value`, no `SystemExit`.
- `test_load_config_file_overrides_defaults` added: `aegis/config.yaml` with `api_url: http://localhost:8000` — asserts override value returned.
- `test_load_config_reads_yaml_and_env`, `test_load_config_raises_when_no_api_key`, `test_api_client_get_raises_on_401` preserved verbatim.

**GREEN:** `cli/config.py::load_config` edited:
- Removed `sys.exit(1)` when `aegis/config.yaml` is absent.
- `cfg` initializes to `{}` unconditionally; the file is read only if it exists.
- `cfg.setdefault("api_url", "https://api.aegis-dq.com")` and `cfg.setdefault("default_profile", "dev")` now apply whether or not a file existed.
- `AEGIS_API_KEY` requirement preserved unchanged (still `sys.exit(1)` if unset).
- All four CLI command callers (`push`, `pull`, `run_cmd`, `status`) are unaffected — they still call `load_config()` and read `cfg["api_url"]` / `cfg["api_key"]` / `cfg["default_profile"]`.

### Task 2: Documentation

**docs/client-lane.md** (new):
- "When to use the client lane": SQLite, on-prem, Snowflake with IP allowlist, MSSQL.
- "Self-run the engine against the hosted dashboard": `pip install "aegis-dq[<db>]"`, set `AEGIS_API_KEY`, provide `database_connection.yaml`. Explains that no `aegis/config.yaml` is needed.
- "Schedule via AegisDQOperator": Airflow DAG snippet using `AegisDQOperator` with env-based config.
- "Snowflake IP allowlist": Railway egress IPs are not static; use client lane or remove the restriction for the read-only service account.

**DEPLOY.md** — "Hosted scheduler" section appended:
- Single-process / single-replica requirement; `AEGIS_SCHEDULER_ENABLED` gate (default 1; set 0 on extra replicas).
- No-Alembic: `schedules` table auto-created by `create_all` on existing Railway Postgres; no ALTER on existing tables.
- Missed runs during downtime are skipped; `next_run_at` rolls forward one interval.
- Snowflake IP allowlist limitation with link to `docs/client-lane.md`.

**README.md**: "Running the Engine from Your Own Environment (Client Lane)" section added, pointing to `docs/client-lane.md`.

**.gitignore**: `docs/` exclusion narrowed to `docs/superpowers/` so `docs/client-lane.md` is tracked in the repo (was required by the Settings locked notice link target `/docs/client-lane`).

## Verification Results

- `pytest tests/test_cli/test_config.py -q` — 5 passed
- `pytest tests/ -q` — 68 passed (0 failures; +1 net new test over 67 baseline)
- `python -c "..."` verification assertion for docs content — passed (AegisDQOperator in client-lane.md, AEGIS_API_KEY in client-lane.md, allowlist in both docs, AEGIS_SCHEDULER_ENABLED in DEPLOY.md, create_all in DEPLOY.md, client-lane in README.md)
- `grep "config.yaml" cli/config.py` — shows existence check without exit on absence

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Narrowed .gitignore to allow docs/client-lane.md to be tracked**
- **Found during:** Task 2 commit attempt
- **Issue:** `.gitignore` contained `docs/` which ignored the entire docs directory, making `git add docs/client-lane.md` fail. The intent of the rule was to exclude `docs/superpowers/` (design specs), not all docs.
- **Fix:** Changed `.gitignore` from `docs/` to `docs/superpowers/`. The client-lane runbook is a first-class repo artifact that the Settings locked notice links to — it must be tracked.
- **Files modified:** `.gitignore`
- **Commit:** 76b0aba

## Known Stubs

None.

## Threat Flags

No new security surface. All four STRIDE threats in the plan's threat model addressed:
- T-09E-01: `api_key` still read only from `AEGIS_API_KEY` env; optional `config.yaml` carries `api_url`/`default_profile` only, no secret.
- T-09E-02: Default `api_url` is the documented hosted dashboard; explicit `config.yaml` overrides it; documented in client-lane.md.
- T-09E-03: DEPLOY.md documents the single-replica / `AEGIS_SCHEDULER_ENABLED` invariant explicitly.
- T-09E-04: DEPLOY.md documents `create_all` auto-creates the new `schedules` table; no existing-table ALTER.

## Self-Check: PASSED

- cff11da: git log confirms RED test commit exists
- 928e1fb: git log confirms GREEN implementation commit exists
- 76b0aba: git log confirms Task 2 docs commit exists
- `cli/config.py`: no `sys.exit` on missing config.yaml; `cfg = {}` with conditional file read
- `tests/test_cli/test_config.py`: 5 tests; `test_load_config_without_file_uses_defaults` and `test_load_config_file_overrides_defaults` present; no `test_load_config_raises_when_no_config_yaml`
- `docs/client-lane.md`: created; contains AegisDQOperator, AEGIS_API_KEY, allowlist
- `DEPLOY.md`: contains AEGIS_SCHEDULER_ENABLED, create_all, allowlist
- `README.md`: contains client-lane
- `pytest tests/` — 68 passed
