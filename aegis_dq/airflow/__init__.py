"""aegis_dq.airflow — Airflow integration for Aegis DQ.

Install with: pip install aegis-dq[airflow]

Usage:
    from aegis_dq.airflow import AegisDQOperator
"""
try:
    from airflow.models import BaseOperator  # noqa: F401 — presence check only
except ImportError as exc:
    raise ImportError(
        "aegis_dq.airflow requires Apache Airflow. "
        "Install it with: pip install 'aegis-dq[airflow]'"
    ) from exc

from aegis_dq.airflow._operator import AegisDQOperator

__all__ = ["AegisDQOperator"]
