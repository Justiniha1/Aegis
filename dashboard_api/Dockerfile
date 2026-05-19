FROM python:3.13-slim

WORKDIR /app

# Install dashboard API dependencies
COPY dashboard_api/requirements.txt ./dashboard_api/requirements.txt
RUN pip install --no-cache-dir -r dashboard_api/requirements.txt

# Install backend engine dependencies (pandas is the only addition beyond dashboard_api deps)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source (for in-process TestEngine invocation via run_executor)
COPY backend/ ./backend/

# Copy dashboard API source
COPY dashboard_api/ ./dashboard_api/

# Add /app to PYTHONPATH so both `backend.*` and `dashboard_api.*` are importable
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "dashboard_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
