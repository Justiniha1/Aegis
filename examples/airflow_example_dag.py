"""
Aegis DQ — Example Airflow DAG
================================

Drop this file into your Airflow DAGs folder.
Set one environment variable (or Airflow Variable) on your worker:

    AEGIS_API_KEY   Your Aegis client API key (from Settings -> API Keys)

The Aegis API URL is fixed (the hosted endpoint, baked into the SDK) — you do not configure
it. No other configuration is required on the worker. The DAG will:
  1. Trigger a data-quality run against the "production" connection profile
  2. Wait for all checks to complete (polling every 5 seconds)
  3. Fail this task -- and block downstream tasks -- if any check fails
  4. Pass and continue downstream if all checks pass

To change which profile runs, update the `profile` argument on AegisDQOperator.
To restrict to specific test types, add `type_filter=["null_check", "schema_check"]`.

Install:
    pip install 'aegis-dq[airflow]'
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from aegis_dq.airflow import AegisDQOperator

# ---------------------------------------------------------------------------
# Default task arguments applied to every task in this DAG.
# ---------------------------------------------------------------------------
default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="aegis_dq_example",
    description="Run Aegis data-quality checks before downstream processing",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["aegis", "data-quality"],
) as dag:

    # -----------------------------------------------------------------------
    # Task: run_quality_checks
    #
    # Triggers an Aegis run for the "production" profile.
    # The API key is read from the AEGIS_API_KEY env var (the API URL is fixed).
    # The task FAILS (and blocks downstream) if any check fails.
    # -----------------------------------------------------------------------
    run_quality_checks = AegisDQOperator(
        task_id="run_quality_checks",
        profile="production",         # change to match your connection profile name
        poll_interval=5,              # seconds between status polls
        # To read the key from an Airflow Variable instead of the env var, uncomment:
        # airflow_var_api_key="AEGIS_API_KEY",
    )

    # -----------------------------------------------------------------------
    # Task: downstream_processing
    #
    # This task only runs when run_quality_checks passes.
    # Replace the body with your actual downstream logic.
    # -----------------------------------------------------------------------
    def _run_downstream(**context):
        run_result = context["ti"].xcom_pull(task_ids="run_quality_checks")
        print(
            f"Quality checks passed -- run_id={run_result.get('id')}, "
            f"tests={run_result.get('total_tests')} -- proceeding with downstream."
        )

    downstream_processing = PythonOperator(
        task_id="downstream_processing",
        python_callable=_run_downstream,
    )

    # -----------------------------------------------------------------------
    # Dependency: downstream_processing runs ONLY after run_quality_checks passes
    # -----------------------------------------------------------------------
    run_quality_checks >> downstream_processing
