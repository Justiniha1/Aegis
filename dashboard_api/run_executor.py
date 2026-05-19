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
import traceback
from datetime import datetime
from typing import Optional

from dashboard_api import models
from dashboard_api.database import SessionLocal

_MAX_ERROR_REASON_LEN = 500


def _sanitize_error(s: str) -> str:
    """D-17 specificity + log-injection guard: strip CR/LF/control chars, cap length."""
    if not s:
        return ""
    cleaned = s.replace("\r", " ").replace("\n", " ")
    # Strip ASCII control chars 0x00-0x1F except space
    cleaned = "".join(c for c in cleaned if ord(c) >= 32 or c == " ")
    return cleaned[:_MAX_ERROR_REASON_LEN]


def _persist_result(db, client_id: int, run_id: int, result: dict) -> None:
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
            metrics=result.get("metrics") or {},
            message=result.get("message") or "",
            run_at=datetime.utcnow(),
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
    # Import here to keep module load fast and avoid cycle risk at api boot.
    from backend.core.config_loader import DQFConfig, load_config
    from backend.core.test_engine import TestEngine

    db = SessionLocal()
    try:
        run = db.query(models.Run).filter(models.Run.id == run_id).first()
        if run is None:
            print(f"[warn] execute_run: run_id={run_id} not found — aborting")
            return

        # Flip QUEUED -> RUNNING
        run.status = "RUNNING"
        db.commit()

        try:
            # Load engine config from YAML (same path the CLI engine uses).
            # config_loader respects DQF_CONNECTION_YAML_PATH via CONFIG_DIR — set in compose env.
            config = load_config()
        except FileNotFoundError as e:
            # D-14 Type-a "didn't start" — profile config missing.
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"Engine config missing — {type(e).__name__}: {e}"
            )
            run.completed_at = datetime.utcnow()
            db.commit()
            return
        except Exception as e:
            # D-14 Type-a — couldn't even load config.
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"Engine config load failed — {type(e).__name__}: {e}"
            )
            run.completed_at = datetime.utcnow()
            db.commit()
            return

        # Validate profile reachable (in the loaded connections dict).
        if profile not in config.connections:
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"Profile {profile} not reachable — not present in database_connection.yaml"
            )
            run.completed_at = datetime.utcnow()
            db.commit()
            return

        # Apply type_filter — narrow config.tests to those matching profile + filter.
        filtered_tests = [
            t for t in config.tests
            if t.enabled and t.profile == profile
            and (type_filter is None or t.type in type_filter)
        ]
        if not filtered_tests:
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"No tests enabled for profile {profile}"
                + (f" with type_filter {type_filter}" if type_filter else "")
            )
            run.completed_at = datetime.utcnow()
            db.commit()
            return

        # Rebuild a narrowed DQFConfig.
        narrowed = DQFConfig(
            engine=config.engine,
            connections=config.connections,
            tests=filtered_tests,
        )

        # Update total (it may differ from the value computed at POST time if YAML changed).
        run.total_tests = len(filtered_tests)
        db.commit()

        engine = TestEngine(narrowed)

        # Tracks which test we're at, for D-15 Type-b mid-run error reporting.
        state = {"idx": 0}

        def on_result(result: dict) -> None:
            state["idx"] += 1
            _persist_result(db, client_id, run_id, result)

        try:
            engine.run(on_result=on_result)
        except Exception as e:
            # D-15 Type-b — engine crashed mid-run. Partial results already persisted via on_result.
            tb = traceback.format_exc(limit=3)
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"Engine crashed at test {state['idx']} — {type(e).__name__}: {e}"
            )
            run.error_at_test = state["idx"]
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
