"""AegisDQOperator — Airflow BaseOperator that runs Aegis data-quality checks.

Credentials resolution order (for both api_url and api_key):
  1. Constructor argument (api_url= / api_key=)
  2. Airflow Variable (airflow_var_api_url= / airflow_var_api_key=)
  3. Environment variable AEGIS_API_URL / AEGIS_API_KEY
"""
from __future__ import annotations

from typing import Any, Sequence

from airflow.models import BaseOperator

from aegis_dq._run import AegisDQChecksFailed, run_checks


class AegisDQOperator(BaseOperator):
    """Airflow operator that triggers an Aegis data-quality run.

    The task fails (raises AegisDQChecksFailed) when any check fails,
    blocking all downstream tasks in the DAG.

    Args:
        profile:            Connection profile name to run.
        type_filter:        Optional list of test type names to restrict the run.
        poll_interval:      Seconds between API status polls (default: 5).
        max_wait_seconds:  Hard deadline in seconds passed to run_checks(). Raises
                           AegisDQRunTimeout if the run has not completed within this
                           deadline. Supports Jinja templating. None (default) polls
                           indefinitely.
        api_url:            Aegis API base URL. Overrides AEGIS_API_URL env var.
        api_key:            Aegis API key. Overrides AEGIS_API_KEY env var.
        airflow_var_api_url: Airflow Variable name holding the API URL.
                            Checked after api_url but before AEGIS_API_URL env var.
        airflow_var_api_key: Airflow Variable name holding the API key.
                            Checked after api_key but before AEGIS_API_KEY env var.
        **kwargs:           Forwarded to BaseOperator (task_id, dag, retries, etc.)
    """

    # Airflow uses template_fields to allow Jinja templating in task params.
    template_fields: Sequence[str] = ("profile", "max_wait_seconds")

    def __init__(
        self,
        *,
        profile: str = "default",
        type_filter: list[str] | None = None,
        poll_interval: int = 5,
        max_wait_seconds: int | None = None,
        api_url: str | None = None,
        api_key: str | None = None,
        airflow_var_api_url: str | None = None,
        airflow_var_api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.profile = profile
        self.type_filter = type_filter
        self.poll_interval = poll_interval
        self.max_wait_seconds = max_wait_seconds
        self._api_url = api_url
        self._api_key = api_key
        self._airflow_var_api_url = airflow_var_api_url
        self._airflow_var_api_key = airflow_var_api_key

    def _resolve_api_url(self) -> str | None:
        """Resolve API URL: constructor arg > Airflow Variable > env var (env read in AegisAPIClient)."""
        if self._api_url:
            return self._api_url
        if self._airflow_var_api_url:
            try:
                from airflow.models import Variable
                return Variable.get(self._airflow_var_api_url, default_var=None)
            except Exception:
                pass
        return None  # AegisAPIClient will read AEGIS_API_URL from env

    def _resolve_api_key(self) -> str | None:
        """Resolve API key: constructor arg > Airflow Variable > env var (env read in AegisAPIClient)."""
        if self._api_key:
            return self._api_key
        if self._airflow_var_api_key:
            try:
                from airflow.models import Variable
                return Variable.get(self._airflow_var_api_key, default_var=None)
            except Exception:
                pass
        return None  # AegisAPIClient will read AEGIS_API_KEY from env

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the data-quality run.

        Returns:
            The final run dict from the Aegis API.

        Raises:
            AegisDQChecksFailed: When any check fails. Airflow marks task as failed.
            ValueError:          When API credentials cannot be resolved.
            requests.HTTPError:  On API 4xx/5xx responses.
        """
        self.log.info(
            "AegisDQOperator: triggering run for profile '%s'", self.profile
        )

        resolved_url = self._resolve_api_url()
        resolved_key = self._resolve_api_key()

        try:
            result = run_checks(
                profile=self.profile,
                type_filter=self.type_filter,
                poll_interval=self.poll_interval,
                api_url=resolved_url,
                api_key=resolved_key,
                max_wait_seconds=self.max_wait_seconds,
            )
        except AegisDQChecksFailed as exc:
            self.log.error(
                "AegisDQOperator: checks FAILED — run_id=%s, reason=%s",
                exc.run_id,
                exc.reason,
            )
            raise  # re-raise so Airflow marks task as failed

        self.log.info(
            "AegisDQOperator: run %s COMPLETE — %s/%s tests passed",
            result.get("id"),
            result.get("completed_tests"),
            result.get("total_tests"),
        )
        return result
