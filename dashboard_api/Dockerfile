FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./dashboard_api/

EXPOSE 8000

CMD ["uvicorn", "dashboard_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
