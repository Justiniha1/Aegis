ifneq (,$(wildcard .env))
  include .env
  export
endif

.PHONY: start stop seed run build logs clean help

help:
	@echo ""
	@echo "  Comet Data Quality Framework"
	@echo ""
	@echo "  make start   — Start the dashboard (API + frontend)"
	@echo "  make seed    — Load demo data and run the engine once"
	@echo "  make run     — Run the test engine against your databases"
	@echo "  make stop    — Stop all services"
	@echo "  make build   — Rebuild containers after code changes"
	@echo "  make logs    — Tail service logs"
	@echo "  make clean   — Full teardown including database"
	@echo ""

start:
	docker-compose up -d api frontend
	@echo ""
	@echo "  Dashboard: http://localhost:3000"
	@echo "  API docs:  http://localhost:8000/docs"
	@echo ""
	@echo "  Run 'make seed' to load demo data and create your account."
	@echo ""

seed:
	python Scripts/seed.py

run:
	python backend/main.py

stop:
	docker-compose down

build:
	docker-compose build

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	rm -f db_data/dashboard.db
