from __future__ import annotations

from datetime import datetime

from airflow import DAG

from comet_dq.airflow import CometDQOperator

with DAG(
    dag_id="comet_demo",
    description="Demo: trigger an Comet data-quality run on the hosted website",
    schedule=None,             
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["comet", "demo"],
) as dag:

    run_demo_quality_checks = CometDQOperator(
        task_id="run_demo_quality_checks",
        profile="demo",    
        poll_interval=5,       

    )
