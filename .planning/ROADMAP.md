# Roadmap: Aegis

## Milestones

- ✅ **v1.0 Demo Readiness** — Phases 1–2 (shipped 2026-05-22)
- ✅ **v1.1 First Client: Airflow Integration** — Phases 3–4 (shipped 2026-05-26)
- 🔄 **v1.2 First Client Handoff** — Phases 5–7 (in progress)

## Phases

<details>
<summary>✅ v1.0 Demo Readiness (Phases 1–2) — SHIPPED 2026-05-22</summary>

- [x] Phase 1: Demo Readiness (7/7 plans) — signed off 2026-05-17
- [x] Phase 1.1: Frontend Design Pass (INSERTED) (6/6 plans) — signed off 2026-05-17
- [x] Phase 2: Run-from-UI (2/2 plans) — substantially complete 2026-05-22; profile switcher + per-row triggers deferred

</details>

<details>
<summary>✅ v1.1 First Client: Airflow Integration (Phases 3–4) — SHIPPED 2026-05-26</summary>

- [x] Phase 3: Package + Airflow (3/3 plans) — complete 2026-05-24
- [x] Phase 4: Production Hardening (2/2 plans) — complete 2026-05-26

</details>

### v1.2 First Client Handoff

- [x] **Phase 5: SDK Reliability** — `run_checks()` timeout parameter + operator passthrough (complete 2026-05-27)
- [x] **Phase 6: Profile Switcher UI** — Settings page component for selecting active connection profile (complete 2026-05-29)
- [ ] **Phase 7: Railway Deployment** — `railway.toml`, one-click deploy button, post-deploy README checklist

## Phase Details

### Phase 5: SDK Reliability
**Goal**: Airflow users can set a hard deadline on `run_checks()` so DAG tasks never hang indefinitely
**Depends on**: Phase 4 (production-hardened API, `run_checks()` and `AegisDQOperator` exist)
**Requirements**: SDK-01, SDK-02
**Success Criteria** (what must be TRUE):
  1. `run_checks(max_wait_seconds=60)` raises `AegisDQRunTimeout` if the run has not reached a terminal state within 60 seconds
  2. `run_checks()` called without `max_wait_seconds` continues to poll indefinitely (backward-compatible)
  3. `AegisDQOperator(max_wait_seconds=120)` passes the timeout through to `run_checks()` without modification
  4. `AegisDQOperator` exposes `max_wait_seconds` as a Jinja-templatable field so DAG authors can parameterise it
**Plans**: 3 plans (2 waves)
Plans:

**Wave 1**
- [ ] 05-01-PLAN.md — Add AegisDQRunTimeout exception and wire max_wait_seconds through _client.py and _run.py

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 05-02-PLAN.md — Unit tests for AegisDQRunTimeout timeout behavior (TDD)
- [ ] 05-03-PLAN.md — Add max_wait_seconds to AegisDQOperator constructor, template_fields, and execute()

Cross-cutting constraints:
- `max_wait_seconds: int | None = None` default is the same across all three plans (no breaking change)

### Phase 6: Profile Switcher UI
**Goal**: Operators with multiple connection profiles can pick the active profile from the Settings page before triggering a run
**Depends on**: Phase 2 (profiles endpoint exists, run context in place), Phase 4 (Docker env vars stable)
**Requirements**: UX-01
**Success Criteria** (what must be TRUE):
  1. The Settings page shows all available connection profiles fetched from the API
  2. Operator can click a profile to mark it active; the selection is reflected in the run context
  3. A subsequent run trigger from the TopBar uses the selected profile, not a hardcoded default
  4. Active profile selection persists across page navigations within the session
**Plans**: 1 plan (1 wave)

Plans:

**Wave 1**
- [x] 06-01-PLAN.md — Extend RunContext with profilesLoading/profilesError; update settings/page.tsx (opacity, state branches, labels, error copy)

### Phase 7: Railway Deployment
**Goal**: Anyone can deploy Aegis to Railway in under 15 minutes using only the README
**Depends on**: Phase 5, Phase 6 (all v1.2 features complete before public handoff)
**Requirements**: DEPLOY-03, DEPLOY-04, DEPLOY-05
**Success Criteria** (what must be TRUE):
  1. Clicking the "Deploy on Railway" button in the README starts a Railway project with `api`, `frontend`, and `engine` services pre-configured — no code changes required
  2. After setting the documented env vars, `https://<project>.railway.app` serves the Aegis dashboard login page
  3. `railway.toml` correctly specifies Dockerfile paths, start commands, and port bindings for all three services
  4. The README post-deploy checklist covers: required env vars, creating the first client account, and pointing an Airflow worker at the live API URL
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Demo Readiness | v1.0 | 7/7 | Complete | 2026-05-17 |
| 1.1. Frontend Design Pass (INSERTED) | v1.0 | 6/6 | Complete | 2026-05-17 |
| 2. Run-from-UI | v1.0 | 2/2 | Substantially complete | 2026-05-22 |
| 3. Package + Airflow | v1.1 | 3/3 | Complete | 2026-05-24 |
| 4. Production Hardening | v1.1 | 2/2 | Complete | 2026-05-26 |
| 5. SDK Reliability | v1.2 | 3/3 | Complete | 2026-05-27 |
| 6. Profile Switcher UI | v1.2 | 1/1 | Complete | 2026-05-29 |
| 7. Railway Deployment | v1.2 | 0/? | Not started | - |

---
*Roadmap created: 2026-05-07*
*Last updated: 2026-05-29 — Phase 6 complete (1/1 plans)*
