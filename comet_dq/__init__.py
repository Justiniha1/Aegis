"""comet_dq — public API for the Comet data-quality engine.

Public surface:
    run_checks()              — trigger a run and raise on failure
    CometDQChecksFailed       — exception raised when checks fail
    CometDQRunTimeout         — exception raised when max_wait_seconds is exceeded
    airflow.CometDQOperator  — Airflow operator (pip install comet-dq[airflow])

Internal modules (_client, _run, airflow) are not part of the stable API.
"""
from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["run_checks", "CometDQChecksFailed", "CometDQRunTimeout", "__version__"]

from comet_dq._run import CometDQChecksFailed, CometDQRunTimeout, run_checks
