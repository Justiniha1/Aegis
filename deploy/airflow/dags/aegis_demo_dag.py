# deploy/airflow/dags/aegis_demo_dag.py
"""Aegis demo DAG — triggers a real run on the hosted Aegis website.

Baked into the demo Airflow image. Triggered manually during a sales demo.
Credentials come from the service env: AEGIS_API_URL and AEGIS_API_KEY.
"""
from __future__ import annotations

from datetime import datetime

from airflow import DAG

from aegis_dq.airflow import AegisDQOperator

with DAG(
    dag_id="aegis_demo",
    description="Demo: trigger an Aegis data-quality run on the hosted website",
    schedule=None,                 # manual trigger only — presenter clicks Run
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["aegis", "demo"],
) as dag:

    run_demo_quality_checks = AegisDQOperator(
        task_id="run_demo_quality_checks",
        profile="demo",            # the seeded Postgres profile on the hosted account
        poll_interval=5,           # seconds between status polls
        # AEGIS_API_URL / AEGIS_API_KEY are read from the service environment.
    )
