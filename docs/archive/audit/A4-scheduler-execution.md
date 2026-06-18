# A4 Audit — Run-Execution and Scheduling Subsystem

Scope (read in full): `dashboard_api/scheduler.py`, `dashboard_api/run_executor.py`,
`dashboard_api/schedule_logic.py`, `dashboard_api/yaml_sync.py`.
Context only: `dashboard_api/models.py` (Run/Schedule), `backend/core/test_engine.py`,
`dashboard_api/queries.py` (`active_run`, `enabled_tests_query`),
`dashboard_api/routers/runs.py` (manual-trigger path), `dashboard_api/connection_source.py`.

This is a read-only audit. No source files were modified. Behavior-preserving disposition is
noted per finding; anything that would change observable behavior is marked `ask-first`.

## Summary

The scheduling design is deliberate and unusually well-documented for a prototype: a single
in-process `AsyncIOScheduler`, the `Schedule` table as the only durable store, single-step
roll-forward (no catch-up burst), and per-row session isolation. The core loop is correct for
the stated single-process / single-replica deployment, and the existing test suite covers the
headline behaviors (dispatch, skip-not-due, skip-disabled, active-run skip, skip-missed,
loop-resilience, stuck-QUEUED recovery, last_run_at gating).

The residual risk is concentrated in concurrency and idempotency at the *boundaries* of that
assumption. The active-run guard is a read-then-write with no DB-level lock or unique
constraint, so the scheduler and the manual `POST /runs` path can both pass the guard and
create two concurrent runs for one client; the documented `max_instances=1` only prevents two
*pollers* from overlapping, not poller-vs-request. Dispatch is `await`-ed inside the per-row
loop, so one slow `execute_run` serializes (and delays) every other due schedule in the same
tick. `datetime.utcnow()` is used throughout and is deprecated in 3.12; the naive-UTC
convention is internally consistent but brittle. None of these are crashing bugs today, but all
must be understood and pinned with characterization tests before any refactor, because the
"it's single-process so it's safe" invariant is load-bearing and invisible.

The 4-file split is *mostly* justified (pure logic vs. runtime vs. executor vs. YAML), but
`yaml_sync.py` is unrelated to scheduling/execution and only landed in this area by directory
adjacency — it should not be coupled into a scheduler refactor.

## Findings

### [High] Active-run guard is a non-atomic read-then-write — scheduler can race the manual trigger
Location: `dashboard_api/scheduler.py:74-85`; cross-path `dashboard_api/routers/runs.py:100-117`;
guard def `dashboard_api/queries.py:39-49`.
What & why: `poll_due_schedules` does `if active_run(db, sched.client_id) is None:` then
`db.add(run); db.commit()`. `active_run` is a plain SELECT on `status IN (QUEUED, RUNNING)`;
there is no row lock, no `SELECT ... FOR UPDATE`, and no unique/partial index enforcing
"at most one active run per client." `max_instances=1` + `coalesce=True`
(`scheduler.py:144-145`) only serialize the poller against itself. They do **not** serialize the
poller against a concurrent `POST /api/v1/runs`, which runs the identical unguarded
read-then-write in the request thread. Interleaving (scheduler reads None, request reads None,
both insert) yields two simultaneous `RUNNING` runs for one client — exactly what D-09 is meant
to forbid. On SQLite the write lock narrows but does not close the window (the two SELECTs both
complete before either INSERT). The `uq_schedule_client_profile` constraint is on schedules, not
runs, so it does not help here.
Recommendation: enforce the invariant in the database, not in application code. Add a partial
unique index on `runs(client_id) WHERE status IN ('QUEUED','RUNNING')` (Postgres) or an
equivalent guard table, and treat the IntegrityError as "already active." Alternatively take an
advisory/row lock around the guard. Keep the in-app check as a fast-path. Document that until
then, the guard is best-effort.
Disposition: `ask-first` (schema/migration change; alters failure mode from silent double-run to
a caught IntegrityError).

### [High] Dispatch is awaited inside the per-row loop — one slow run starves all other due schedules
Location: `dashboard_api/scheduler.py:64-94` (loop), `:88-94` (`await run_in_threadpool(execute_run, ...)`).
What & why: `execute_run` is the *entire* engine run (full pandas/SQL test pass), and it is
`await`-ed per due schedule before the loop advances to the next `sched_id`. The threadpool
keeps it off the event loop, but the poll coroutine itself does not proceed until that run
finishes. With N clients due in the same tick, client N's run is not even dispatched until
clients 1..N-1 have fully *completed*. A single long-running client run (minutes) therefore
delays dispatch — and the `next_run_at` roll-forward — of every other client in that tick. The
module docstring frames `execute_run` dispatch as fire-and-forth ("dispatched via
run_in_threadpool so it never blocks the event loop"), but awaiting it makes the tick duration
the sum of all run durations, not the max. This contradicts the apparent intent and does not
scale past a single active client. (Note the manual path at `runs.py:131-137` instead uses
`BackgroundTasks.add_task`, which is genuinely fire-and-forget — the two paths have different
concurrency semantics for the same `execute_run`.)
Recommendation: dispatch without awaiting completion — e.g. schedule the threadpool call as a
fire-and-forget task (`asyncio.create_task` wrapping the threadpool call) so the loop only blocks
on the Run-row INSERT, not on engine execution; or move `next_run_at` advance to occur *before*
awaiting. Behavior change either way — must be characterized first. Confirm intended semantics.
Disposition: `ask-first` (changes when `next_run_at`/`last_run_at` are committed relative to run
completion; observable to monitoring).

### [Medium] `datetime.utcnow()` used throughout — deprecated in 3.12 and timezone-fragile
Location: `scheduler.py:46,106,115,123`; `run_executor.py:118,144,177,197,204`;
`schedule_logic.py:64`; `models.py` defaults (`started_at`, `created_at`, etc.).
What & why: `datetime.utcnow()` is deprecated as of Python 3.12 (the codebase runs cpython-3.12
per the `__pycache__`). It returns a *naive* datetime, and the entire subsystem leans on the
"all datetimes are naive UTC" convention (documented in `schedule_logic.py:3`). This works only
as long as nothing ever introduces a tz-aware datetime — e.g. APScheduler is configured
`timezone="UTC"` (`scheduler.py:30`), and any future use of `datetime.now(timezone.utc)` would
make naive/aware comparisons raise `TypeError`. The convention is correct but undefended: a
single tz-aware value entering `compute_next_run(now=...)` or a `next_run_at` filter would
break comparison silently or loudly.
Recommendation: migrate to `datetime.now(timezone.utc)` *and* standardize storage as tz-aware
UTC, OR keep naive-UTC but centralize a single `_utcnow()` helper so the convention is
enforced in one place and the deprecation is silenced once. Either is a cross-cutting change;
the naive-vs-aware decision must be made consistently across models + logic + loop.
Disposition: `ask-first` (cross-cutting; naive↔aware switch changes comparison/serialization
behavior). A pure `utcnow()`→helper rename that preserves naive-UTC is `auto-fix-safe`.

### [Medium] Scheduler-created Run omits `type_filter` and relies on model default for `started_at`; field drift vs. manual path
Location: `scheduler.py:75-83` (Run construction) vs. `runs.py:108-116`.
What & why: The scheduler builds `Run(... type_filter=None ...)` and never sets `started_at`;
it depends on the `models.Run.started_at` server-side default (`models.py:33`,
`default=datetime.utcnow`). That default fires at INSERT/flush time, which is fine, but it means
the "when did this scheduled run start" timestamp is the *queue* time, identical to the manual
path — acceptable, but undocumented. More notably, the scheduler hard-codes `type_filter=None`
(full run) with no way for a schedule to request a typed subset, while the manual path threads a
validated `type_filter`. If schedules ever need type filtering this is a silent capability gap,
not a bug. Also: the manual path validates `profile` against the connection YAML before creating
the run (`runs.py:91-96`); the scheduler trusts `sched.profile` blindly and lets `execute_run`
fail the run later (`run_executor.py:113-120`). Net effect: a stale/renamed profile on a schedule
produces a FAILED run every interval rather than being caught at schedule-edit time.
Recommendation: document that schedules are intentionally full-profile runs, or add `type_filter`
to the Schedule model if subsetting is desired. Consider validating `sched.profile` against the
client's connection YAML in the poller (or at schedule write time) to avoid recurring FAILED
runs. No behavior change required for the audit.
Disposition: `ask-first` (feature/scope decision).

### [Medium] Skip-missed roll-forward is correct but couples "due now" semantics to poll cadence
Location: `scheduler.py:46,57,116-122`; `schedule_logic.py:66-91`.
What & why: A schedule is due when `next_run_at <= now`, and after firing, `next_run_at` is
recomputed from `now` (not from the *scheduled* slot). For `hourly` this always lands at the top
of the next hour; for `daily`/`weekly` it lands at the next configured clock slot relative to
`now`. This is the documented "skip-missed, no catch-up" behavior and matches APScheduler's
`coalesce=True` philosophy (collapse all misses into one) rather than Airflow `catchup=True`
(backfill every interval). The subtle consequence: because roll-forward anchors on `now` (the
actual fire time, which is poll-cadence-quantized to ~60s) rather than on the *intended*
`next_run_at`, fire times drift by up to one poll interval each cycle. For hourly this is masked
(it snaps to `:00`), but a `daily at 06:00` schedule that fires at `06:00:43` recomputes from
`06:00:43`, gets `tomorrow 06:00` — fine. There is no actual drift for clock-aligned presets
because `compute_next_run` snaps to the configured `at_hour:at_minute`. Confirmed: no drift bug.
The note is that the design is correct *only because* every preset is clock-anchored; an
interval-based preset (the reserved `interval_seconds` column, `models.py:96`) would drift.
Recommendation: leave as-is; add a comment that roll-forward correctness depends on presets being
clock-anchored, and that `interval_seconds` is not wired (see Incomplete-features below).
Disposition: `auto-fix-safe` (comment only) — no logic change.

### [Low] Reserved `interval_seconds` / `cron` columns are unused dead surface
Location: `models.py:95-97` (`cron`, `interval_seconds`, `preset`); `schedule_logic.py:11-31`
(`preset_to_cron`); `scheduler.py:116-122` (only `preset` path is honored).
What & why: The poller only ever calls `compute_next_run(sched.preset, ...)`. `interval_seconds`
is documented "reserved; presets use cron" and is never read. `cron` is stored
(`preset_to_cron`) for human inspection but is never parsed back — there is no croniter
dependency (`schedule_logic.py:4`), so the canonical cron string and the actual `compute_next_run`
math are two independent encodings of the same intent that could silently diverge if one is
edited without the other. `preset_to_cron`'s output is effectively write-only display data.
Recommendation: keep, but note in the audit that `cron` is descriptive-only and not the source of
truth (`next_run_at` + `preset` are). If a future milestone wants real cron, adopt croniter and
make `cron` authoritative; until then, treat divergence between `cron` and `preset` as a display
bug, not an execution bug.
Disposition: `auto-fix-safe` (doc/comment); removing the columns is `ask-first` (migration).

### [Low] `print()`-based logging in the loop and executor; no structured log / metrics
Location: `scheduler.py:127`; `run_executor.py:73,102,170,199`.
What & why: Errors and warnings (loop-level failures, stuck-run recovery, per-test persist
failures, mid-run engine crashes) go to `print()`. There is no logger, no level, no run/client
context fields. For a subsystem whose whole safety story is "it silently rolls forward and
isolates errors," the *observability* of those silent paths is weak — a per-tick failure for one
client is a single stdout line with no severity. This is a best-practice gap, not a bug.
Recommendation: replace `print` with the stdlib `logging` module at appropriate levels, including
`run_id`/`client_id`/`sched_id`. Behavior-preserving.
Disposition: `auto-fix-safe`.

### [Low] No retry/backoff; a profile that always FAILs produces one FAILED run per interval forever
Location: `scheduler.py:64-124` + `run_executor.py:113-146`.
What & why: There is intentionally no retry (matches the "skip-missed" philosophy), but there is
also no suppression of *repeated* deterministic failures. A schedule whose profile is missing or
whose tests are all disabled will create a fresh FAILED run on every interval indefinitely
(`run_executor.py:113-120`, `:138-146`), with no escalation, alerting, or auto-disable. For a
demo this is acceptable; at scale it is unbounded FAILED-row growth and alert fatigue.
Recommendation: optionally auto-disable a schedule after K consecutive FAILED runs, or surface a
"schedule unhealthy" flag. Out of scope for a behavior-preserving refactor; flag only.
Disposition: `ask-first` (feature).

### [Low] Per-test persist swallows all exceptions, so `completed_tests` can silently undercount
Location: `run_executor.py:47-77` (esp. `:72-77`).
What & why: `_persist_result` catches every exception and rolls back, by design (D-23 spirit), so
one bad result row does not kill the run. The documented tradeoff is that `completed_tests` "may
briefly lag." But on a persist failure the row is *lost permanently* (no retry), and the run can
still be marked `COMPLETE` (`run_executor.py:203-205`) with `completed_tests < total_tests` and
missing `TestResult` rows. The UI grouping keys on `run_at` (`run_executor.py:175-177`), so a
dropped row just vanishes. This is an accepted-risk design choice, but it is worth an explicit
characterization test so a refactor doesn't accidentally tighten or loosen it.
Recommendation: keep behavior; add a test pinning "persist failure → run still COMPLETE,
completed_tests undercounts, no raise." Consider logging a final reconciliation warning when
`completed_tests != total_tests` at completion.
Disposition: `auto-fix-safe` (test + optional warning log).

## Security

- Cross-tenant isolation in the scheduler is sound: every Run is created with
  `client_id=sched.client_id` (`scheduler.py:76`), `active_run` is filtered by `client_id`
  (`queries.py:42-46`), and `execute_run` resolves tests via `enabled_tests_query(db, client_id,
  profile, ...)` (`run_executor.py:132-136`, `queries.py:28-37`). No code path lets one client's
  schedule read or run against another client's tests or connection config. The
  `get_yaml_text(db, client_id)` call (`run_executor.py:111`) is client-scoped. No tenant-crossing
  found.
- YAML injection via `yaml_sync.py`: writes use `yaml.dump` (not exec), and reads in
  `connection_source._parse` use `yaml.safe_load` (`connection_source.py:32,48`). `safe_load`
  blocks arbitrary-object construction, so a malicious uploaded connection YAML cannot execute
  code. `export_tests_to_yaml` writes atomically via temp-file + `replace` (`yaml_sync.py:88-97`),
  avoiding torn files. One note: `_build_output_dict` preserves the existing file's `engine` and
  `settings` sections verbatim (`yaml_sync.py:70-75`) — if that on-disk file is attacker-influenced
  and later consumed by an unsafe loader elsewhere, the preserved blob is passed through unvalidated.
  Within this subsystem it is safe (`safe_load` on read). Flag for the engine-side auditor (A1).
- `resolve_profile` runs `_resolve_env_vars` on the parsed config (`connection_source.py:64-66`).
  A client-supplied connection YAML containing `${SOME_ENV}` could surface host environment
  variables into the resolved connection dict. This is the documented env-var feature, but it is a
  cross-cutting secret-exposure surface worth confirming is intended for client-uploaded configs.
  Out of A4's direct files; flag to A2 (API/security).
- The scheduler `profile` value flows into `enabled_tests_query` as a parameterized SQLAlchemy
  filter (`queries.py:31-34`) — no string interpolation into SQL. No injection via `profile`.

## Simplification & structure

- The 4-file split is largely justified: `schedule_logic.py` is pure, dependency-free, and
  trivially unit-testable (good); `scheduler.py` is the APScheduler runtime; `run_executor.py` is
  the engine bridge. These three have a clean dependency direction (scheduler → run_executor →
  engine; scheduler → schedule_logic). Keep this separation.
- `yaml_sync.py` does **not** belong to the scheduling/execution subsystem — it is DB→YAML export
  for the tests router and is unrelated to runs/schedules. It is in this audit only by directory
  adjacency. A scheduler refactor should not touch it. Recommend treating it as out-of-area.
- Duplication to address in a refactor: the Run-construction + active-run-guard logic exists in
  two places (`scheduler.py:73-85` and `runs.py:100-117`) with subtly different validation
  (manual path validates profile + type_filter up front; scheduler does not). Extracting a single
  `create_run_if_none_active(db, client_id, profile, type_filter)` helper would remove the drift
  and is the natural home for the DB-level guard fix (High finding above). Behavior-preserving
  extraction is feasible but the two paths' validation differences must be reconciled deliberately,
  not silently merged.
- `compute_next_run`'s trailing `raise ValueError(...)  # pragma: no cover` (`schedule_logic.py:94`)
  is genuinely unreachable (preset is validated at `:58`). Harmless; could be a bare `assert False`
  but not worth churning.
- The dispatch-failure recovery block (`scheduler.py:95-108`) is the single most intricate piece of
  logic in the area (commit QUEUED → dispatch → on failure re-query and force FAILED). It is correct
  and well-tested (Test 7) but reads as "clever." A comment-level cross-reference to the active-run
  guard it protects would help; the logic itself should not be simplified away.

## Test gaps & proposed tests

Existing coverage (`test_scheduler.py` 1-8, `test_schedule_logic.py`, `test_run_executor.py`) is
strong on the happy paths and the documented pitfalls. Gaps to pin *before* refactoring:

1. **Poller-vs-manual-trigger race (High finding).** Characterize current behavior: with the
   active-run guard passing in both, two runs CAN be created. Write a test that creates a run via
   the scheduler path and a run via the `runs.py` create logic with no active run in between, and
   assert the *current* outcome (two active runs). This pins the pre-fix behavior so the DB-guard
   fix has a visible before/after. (`scheduler.py:74-85`, `runs.py:100-117`.)

2. **Multiple due schedules in one tick are processed serially and all advance.** Seed 3 clients,
   all due, assert all 3 get a QUEUED run and all 3 `next_run_at` advance in a single
   `poll_due_schedules()` call. Currently untested (Test 6 uses only 2, and one fails). Also pins
   the await-serialization behavior for the High dispatch finding. (`scheduler.py:64-124`.)

3. **`daily`/`weekly` roll-forward when extremely overdue lands on the correct future clock slot.**
   `test_poll_skips_missed_no_catchup` only covers hourly. Add: daily schedule with `next_run_at`
   30 days in the past fires once and `next_run_at` == next `at_hour:at_minute` after `now` (not
   30 days of catch-up, and not a past slot). Same for weekly across a `weekday` boundary.
   (`schedule_logic.py:71-91`, `scheduler.py:116-122`.)

4. **`compute_next_run` boundary cases.** now exactly at `at_hour:at_minute` (the `<= now` branch,
   `schedule_logic.py:74,89`); hourly when now is exactly on the hour (`:68`); weekly when today IS
   the target weekday but time has passed (`:89-90`). These branches are reachable but unasserted.

5. **`execute_run`: per-test persist failure → run still COMPLETE, `completed_tests` undercounts,
   no raise** (Low finding). Patch `_persist_result`'s `db.add`/commit to raise for one result,
   feed N results, assert COMPLETE + `completed_tests == N-1` + no exception escapes.
   (`run_executor.py:47-77,203-205`.)

6. **`execute_run`: engine crashes mid-run → FAILED, `error_at_test` == index reached, partial
   results persisted** (D-15 Type-b). Currently `run_executor.py:187-200` is untested; only the
   "profile not found" Type-a path has a test. Patch `engine.run` to emit 2 results then raise on
   the 3rd; assert status FAILED, `error_at_test == 3`, 2 TestResult rows present.

7. **`execute_run`: no enabled tests → FAILED with the specific reason** (`run_executor.py:138-146`)
   and **test-count-changed-after-RUNNING warning path** (`:167-171`). Neither is exercised.

8. **`stop_scheduler`/`start_scheduler` idempotency** (`scheduler.py:136-154`): calling start twice
   does not double-register the job (`replace_existing=True` + `running` guard), and stop when not
   running is a no-op. Quick guard-rail test before touching lifecycle.

9. **`yaml_sync` round-trip / preservation** (if kept in scope): `export_tests_to_yaml` preserves
   `engine`/`settings` and regenerates only `tests`; atomic temp-file rename leaves no `.tmp` on
   success and no partial file on dump failure. (`yaml_sync.py:79-97`.)

## Benchmark note (missed-run / catch-up semantics)

The chosen "roll forward exactly one interval, never backfill" policy matches APScheduler's
`coalesce=True` semantics — collapse all missed executions into a single run on recovery — rather
than Airflow's `catchup=True`, which backfills every missed interval. For a polling,
table-as-source-of-truth design with no per-interval idempotency keys, coalesce-style skip-missed
is the correct and safer choice (a long Railway downtime cannot produce a burst). Worth noting the
subsystem reimplements this by hand (`compute_next_run` from `now`) instead of using APScheduler's
own misfire/coalesce machinery, which is consistent with the "Schedule table is the only durable
store, no APScheduler job store" architecture decision.

Sources:
- [APScheduler base scheduler docs (misfire_grace_time, coalesce)](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- [APScheduler job module](https://apscheduler.readthedocs.io/en/3.x/modules/job.html)
