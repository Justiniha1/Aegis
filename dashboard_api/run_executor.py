"""In-process run executor invoked via FastAPI BackgroundTasks.

Architecture choice rationale: see 02-02-PLAN.md <rationale> block.
In short: a single-operator demo prototype with no concurrent-run requirement
does not justify a broker/worker stack. BackgroundTasks + direct TestEngine
import is ~50 lines and reuses every existing fail-safe.

Boundary contract:
- execute_run is called AFTER POST /api/v1/runs returns 202 to the client
  (BackgroundTasks runs post-response — see FastAPI docs).
- All DB writes happen via a fresh Session (NOT the request's session, which
  is closed by the time the background task runs).
- All engine exceptions are caught and converted to Run.FAILED with a
  D-17-compliant error_reason. The function never raises.
- run_id is threaded into result_handler so per-test results join cleanly.
"""
import re
import traceback
import unicodedata
from datetime import datetime
from typing import Optional

from dashboard_api import models
from dashboard_api.database import SessionLocal
# Reuse the single numpy/pandas-scalar JSON sanitizer (np.int64 etc. -> native Python)
# rather than maintaining a byte-for-byte copy here.
from backend.core.result_handler import _sanitize as _sanitize_metrics

_MAX_ERROR_REASON_LEN = 500


def _sanitize_error(s: str) -> str:
    """D-17 specificity + log-injection guard: strip control/format chars, cap length."""
    if not s:
        return ""
    # Collapse all newline/tab variants to a single space
    cleaned = s.translate(str.maketrans("\r\n\t\x0b\x0c", "     "))
    # Strip all Unicode control (Cc) and format (Cf) category chars, preserving space
    cleaned = "".join(
        c for c in cleaned
        if unicodedata.category(c) not in ("Cc", "Cf", "Cs") or c == " "
    )
    cleaned = re.sub(r" {2,}", " ", cleaned).strip()
    return (cleaned or "[error message contained only non-printable characters]")[:_MAX_ERROR_REASON_LEN]


def _persist_result(db, client_id: int, run_id: int, result: dict, run_at: datetime) -> None:
    """Insert a single TestResult row and bump Run.completed_tests atomically.

    Fail-safe (D-23 spirit): any exception is swallowed so a per-test persist
    failure does not kill the run. The Run.completed_tests counter may briefly
    lag — that is acceptable for a polling-based UI.
    """
    try:
        row = models.TestResult(
            client_id=client_id,
            run_id=run_id,
            test_id=result["test_id"],
            test_name=result["name"],
            test_type=result["type"],
            status=result["status"],
            severity=result["severity"],
            metrics=_sanitize_metrics(result.get("metrics") or {}),
            message=result.get("message") or "",
            run_at=run_at,
        )
        db.add(row)
        run = db.query(models.Run).filter(models.Run.id == run_id).first()
        if run is not None:
            run.completed_tests = run.completed_tests + 1
        db.commit()
    except Exception as e:
        print(f"[warn] _persist_result for run_id={run_id} failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def execute_run(
    run_id: int,
    client_id: int,
    profile: str,
    type_filter: Optional[list[str]],
) -> None:
    """Run the engine for a single run record. Updates status QUEUED->RUNNING->COMPLETE|FAILED.

    This function is invoked by FastAPI BackgroundTasks AFTER POST /api/v1/runs returns.
    It never raises — all exceptions are converted to Run.FAILED with sanitized reason text.
    """
    from backend.core.config_loader import (
        DQFConfig, EngineConfig, build_engine_test, _deduplicate_test_ids,
    )
    from backend.core.test_engine import TestEngine
    from dashboard_api import connection_source
    from dashboard_api.queries import enabled_tests_query

    db = SessionLocal()
    try:
        run = db.query(models.Run).filter(models.Run.id == run_id).first()
        if run is None:
            print(f"[warn] execute_run: run_id={run_id} not found — aborting")
            return

        run.status = "RUNNING"
        db.commit()

        # Resolve the connection from the connection YAML — the same file the engine
        # uses. We pass the raw profile dict through; the engine's DatabaseConnector
        # resolves relative SQLite paths (against the config dir) and connection_url.
        yaml_text = connection_source.get_yaml_text(db, client_id)
        prof = connection_source.resolve_profile(yaml_text, profile)
        if not isinstance(prof, dict):
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"Profile '{profile}' not found in connection config"
            )
            run.completed_at = datetime.utcnow()
            db.commit()
            return

        connections = {profile: prof}
        engine_cfg = EngineConfig(
            engine="simple",
            default_profile=profile,
            default_severity="MEDIUM",
            alerts={},
        )

        # Load tests from DB filtered by profile — each profile is a distinct DB environment.
        # Same filter as the pre-flight count in runs.py, via the shared query builder.
        db_test_rows = (
            enabled_tests_query(db, client_id, profile, type_filter)
            .order_by(models.TestDefinition.created_at.asc())
            .all()
        )

        if not db_test_rows:
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"No enabled tests for profile '{profile}'"
                + (f" with type_filter {type_filter}" if type_filter else "")
            )
            run.completed_at = datetime.utcnow()
            db.commit()
            return

        engine_tests = _deduplicate_test_ids([
            build_engine_test(
                name=t.name,
                type=t.type,
                severity=t.severity,
                profile=t.profile,
                enabled=t.enabled,
                tags=t.tags or [],
                config=t.config or {},
            )
            for t in db_test_rows
        ])

        narrowed = DQFConfig(
            engine=engine_cfg,
            connections=connections,
            tests=engine_tests,
        )

        if run.status == "QUEUED" or run.total_tests == 0:
            run.total_tests = len(engine_tests)
        elif run.total_tests != len(engine_tests):
            print(f"[warn] run_id={run_id} test count changed ({run.total_tests} -> {len(engine_tests)}) after RUNNING — keeping original")
        db.commit()

        engine = TestEngine(narrowed)

        # Single timestamp shared by all results in this run — mirrors the batch path
        # in results.py so the frontend can group them correctly by run_at.
        run_at = datetime.utcnow()

        # Tracks which test we're at, for D-15 Type-b mid-run error reporting.
        idx = 0

        def on_result(result: dict) -> None:
            nonlocal idx
            idx += 1
            _persist_result(db, client_id, run_id, result, run_at)

        try:
            engine.run(on_result=on_result)
        except Exception as e:
            # D-15 Type-b — engine crashed mid-run. Partial results already persisted via on_result.
            tb = traceback.format_exc(limit=3)
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"Engine crashed at test {idx} — {type(e).__name__}: {e}"
            )
            run.error_at_test = idx
            run.completed_at = datetime.utcnow()
            db.commit()
            print(f"[warn] execute_run run_id={run_id} crashed: {tb}")
            return

        # Success — D-12 completion path.
        run.status = "COMPLETE"
        run.completed_at = datetime.utcnow()
        db.commit()

    finally:
        db.close()
