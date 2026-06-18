"""comet_dq.airflow — Airflow integration for Comet DQ.

Install with: pip install comet-dq[airflow]

Usage:
    from comet_dq.airflow import CometDQOperator
"""
try:
    from airflow.models import BaseOperator  # noqa: F401 — presence check only
except ImportError as exc:
    raise ImportError(
        "comet_dq.airflow requires Apache Airflow. "
        "Install it with: pip install 'comet-dq[airflow]'"
    ) from exc

from comet_dq.airflow._operator import CometDQOperator

__all__ = ["CometDQOperator"]
