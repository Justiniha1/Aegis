from __future__ import annotations

from datetime import datetime

from airflow import DAG

from aegis_dq.airflow import AegisDQOperator

with DAG(
    dag_id="aegis_demo",
    description="Demo: trigger an Aegis data-quality run on the hosted website",
    schedule=None,             
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["aegis", "demo"],
) as dag:

    run_demo_quality_checks = AegisDQOperator(
        task_id="run_demo_quality_checks",
        profile="demo",    
        poll_interval=5,       

    )
