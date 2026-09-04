PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: install up down api web test migrate seed revision lint fmt

install:            ## create venv + install backend and frontend deps
	/opt/homebrew/bin/python3.13 -m venv .venv
	$(PIP) install -q -r backend/requirements.txt
	cd frontend && npm install

up:                 ## start Postgres
	docker compose up -d

down:               ## stop Postgres
	docker compose down

api:                ## run the FastAPI server on :8000
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000

web:                ## run the Vite dev server on :5173
	cd frontend && npm run dev

test:               ## run both test suites
	cd backend && ../.venv/bin/pytest -q
	cd frontend && npm run test --silent

migrate:            ## bring the database up to the latest migration
	cd backend && ../.venv/bin/alembic upgrade head

seed:               ## load one deterministic reviewer walkthrough
	cd backend && ../.venv/bin/python -m app.seed

revision:           ## autogenerate a migration from model changes (M="message")
	cd backend && ../.venv/bin/alembic revision --autogenerate -m "$(M)"

lint:               ## report lint findings (config in ruff.toml)
	.venv/bin/ruff check .

fmt:               ## apply the lint fixes that are safe to apply
	.venv/bin/ruff check . --fix
