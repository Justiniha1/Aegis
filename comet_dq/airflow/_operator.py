"""CometDQOperator — Airflow BaseOperator that runs Comet data-quality checks.

API key resolution order:
  1. Constructor argument (api_key=)
  2. Airflow Variable (airflow_var_api_key=)
  3. Environment variable COMET_API_KEY

The API URL is fixed (the hosted Comet endpoint, baked into the SDK) and is not configurable
via environment. The api_url= / airflow_var_api_url= arguments remain only as internal/testing
overrides.
"""
from __future__ import annotations

from typing import Any, Sequence

from airflow.models import BaseOperator, Variable

from comet_dq._run import CometDQChecksFailed, run_checks


class CometDQOperator(BaseOperator):
    """Airflow operator that triggers an Comet data-quality run.

    The task fails (raises CometDQChecksFailed) when any check fails,
    blocking all downstream tasks in the DAG.

    Args:
        profile:            Connection profile name to run.
        type_filter:        Optional list of test type names to restrict the run.
        poll_interval:      Seconds between API status polls (default: 5).
        max_wait_seconds:  Hard deadline in seconds passed to run_checks(). Raises
                           CometDQRunTimeout if the run has not completed within this
                           deadline. Supports Jinja templating. None (default) polls
                           indefinitely.
        api_url:            Internal/testing override for the (fixed) hosted API URL.
        api_key:            Comet API key. Overrides COMET_API_KEY env var.
        airflow_var_api_url: Internal/testing Airflow Variable name holding the API URL.
        airflow_var_api_key: Airflow Variable name holding the API key.
                            Checked after api_key but before COMET_API_KEY env var.
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

    @staticmethod
    def _resolve(direct: str | None, airflow_var: str | None) -> str | None:
        """Resolve a credential: constructor arg > Airflow Variable > None.

        Returning None lets CometAPIClient use its defaults: the baked hosted URL for
        api_url, and the COMET_API_KEY env var for api_key.
        """
        if direct:
            return direct
        if airflow_var:
            try:
                return Variable.get(airflow_var, default_var=None)
            except Exception:
                pass
        return None

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the data-quality run.

        Returns:
            The final run dict from the Comet API.

        Raises:
            CometDQChecksFailed: When any check fails. Airflow marks task as failed.
            ValueError:          When API credentials cannot be resolved.
            requests.HTTPError:  On API 4xx/5xx responses.
        """
        self.log.info(
            "CometDQOperator: triggering run for profile '%s'", self.profile
        )

        resolved_url = self._resolve(self._api_url, self._airflow_var_api_url)
        resolved_key = self._resolve(self._api_key, self._airflow_var_api_key)

        try:
            result = run_checks(
                profile=self.profile,
                type_filter=self.type_filter,
                poll_interval=self.poll_interval,
                api_url=resolved_url,
                api_key=resolved_key,
                max_wait_seconds=self.max_wait_seconds,
            )
        except CometDQChecksFailed as exc:
            self.log.error(
                "CometDQOperator: checks FAILED — run_id=%s, reason=%s",
                exc.run_id,
                exc.reason,
            )
            raise  # re-raise so Airflow marks task as failed

        self.log.info(
            "CometDQOperator: run %s COMPLETE — %s/%s tests passed",
            result.get("id"),
            result.get("completed_tests"),
            result.get("total_tests"),
        )
        return result
