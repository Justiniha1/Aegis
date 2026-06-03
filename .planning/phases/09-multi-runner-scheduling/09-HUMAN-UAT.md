---
status: partial
phase: 09-multi-runner-scheduling
source: [09-VERIFICATION.md]
started: 2026-06-02
updated: 2026-06-02
---

## Current Test

[awaiting human testing]

## Tests

### 1. Settings page live render and schedule lifecycle
expected: On the running dashboard, a website-schedulable profile shows the ScheduleControl (preset picker hourly/daily/weekly, hour/weekday selectors, Active/Paused badge, last/next-run in UTC). Creating, pausing/resuming, and deleting a schedule all work and persist. A SQLite/local profile shows the locked notice (no control) with a working link to /docs/client-lane.
result: [pending]

### 2. Scheduled run fires on the hosted deploy
expected: With AEGIS_SCHEDULER_ENABLED set on Railway, a recurring schedule on a cloud-reachable profile is picked up by poll_due_schedules and dispatched through execute_run within ~60s of its due time; the run appears in run history; missed-during-downtime runs are skipped (not backfilled); no duplicate/overlapping runs.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
