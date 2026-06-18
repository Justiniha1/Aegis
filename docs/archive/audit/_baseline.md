# Audit Baseline — Phase 0

Recorded before any audit/refactor work on branch `refactor/codebase-audit-cleanup`
(based off `feature/error-visualization`).

Date: 2026-06-15

## Test suites (known-good baseline)

These must still pass identically after all refactoring (functionality must be unchanged).

### Python (`python -m pytest -q`)
- **83 passed, 1 skipped**
- 100 warnings (mostly `datetime.utcnow()` deprecation — flagged as a best-practices finding)
- Runtime ~14s

### Frontend (`npx vitest run`, in `frontend/`)
- **27 passed** across 6 test files
- Runtime ~5s

## How to re-verify
```
# repo root
python -m pytest -q
# frontend
cd frontend && npx vitest run
```

Any deviation from the pass counts above after refactoring is a regression and must be
investigated before claiming completion.
