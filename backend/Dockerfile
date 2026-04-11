FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./backend/

# Config and data are mounted at runtime via volumes:
#   -v ./your_config:/app/backend/config
#   -v ./your_data:/app/data  (only needed for SQLite; real DBs connect over network)

CMD ["python", "backend/main.py"]
