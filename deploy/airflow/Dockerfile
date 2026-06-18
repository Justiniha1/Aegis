# deploy/airflow/Dockerfile
# Demo Airflow image: Airflow standalone + the local comet-dq[airflow] package + demo DAG.
# Build context = repo root (see deploy/airflow/railway.toml).
FROM apache/airflow:2.9.3-python3.11

# Bake the demo DAG into the image's DAGs folder.
COPY deploy/airflow/dags/ ${AIRFLOW_HOME}/dags/

# Install the local Comet package with the airflow extra so the operator imports.
# Copy the package sources needed for an editable/local install.
COPY --chown=airflow:root pyproject.toml /opt/comet/pyproject.toml
COPY --chown=airflow:root comet_dq/ /opt/comet/comet_dq/
COPY --chown=airflow:root deploy/airflow/requirements.txt /opt/comet/requirements.txt

USER airflow
RUN pip install --no-cache-dir "/opt/comet" && \
    pip install --no-cache-dir -r /opt/comet/requirements.txt

# Standalone runs webserver + scheduler + triggerer in one process (demo-grade).
ENV AIRFLOW__WEBSERVER__WEB_SERVER_PORT=8080
CMD ["bash", "-c", "airflow standalone"]
