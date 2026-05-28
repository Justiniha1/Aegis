"""aegis_dq — public API for the Aegis data-quality engine.

Public surface:
    run_checks()              — trigger a run and raise on failure
    AegisDQChecksFailed       — exception raised when checks fail
    AegisDQRunTimeout         — exception raised when max_wait_seconds is exceeded
    airflow.AegisDQOperator  — Airflow operator (pip install aegis-dq[airflow])

Internal modules (_client, _run, airflow) are not part of the stable API.
"""
from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["run_checks", "AegisDQChecksFailed", "AegisDQRunTimeout", "__version__"]

from aegis_dq._run import AegisDQChecksFailed, AegisDQRunTimeout, run_checks
