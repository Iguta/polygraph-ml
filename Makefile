.PHONY: dev api worker frontend format lint typecheck test test-backend test-frontend test-e2e contracts benchmarks calibrate-queue live-smoke deployed-smoke deployment-preflight check install

install:
	uv sync --all-groups
	npm --prefix frontend ci
	npm --prefix frontend exec -- playwright install chromium

dev:
	./scripts/dev.sh

api:
	uv run uvicorn polygraphml.api.main:app --reload --host 0.0.0.0 --port 8000

worker:
	uv run python -m polygraphml.worker.main

frontend:
	npm --prefix frontend run dev

format:
	uv run ruff format .
	uv run ruff check --fix .
	npm --prefix frontend run format

lint:
	uv run ruff format --check .
	uv run ruff check .
	npm --prefix frontend run lint

typecheck:
	uv run mypy src
	npm --prefix frontend run typecheck

test: test-backend test-frontend

test-backend:
	uv run pytest --cov=polygraphml --cov-report=term-missing

test-frontend:
	npm --prefix frontend test

test-e2e:
	npm --prefix frontend run test:e2e

contracts:
	uv run python scripts/export_openapi.py

benchmarks:
	uv run polygraphml-benchmarks --output benchmark-results/latest.json

calibrate-queue:
	uv run polygraphml-queue-calibration --input benchmark-results/latest.json --output benchmark-results/queue-timing.json

live-smoke:
	uv run polygraphml-live-smoke --output benchmark-results/live-trace.json

deployed-smoke:
	@test -n "$(API_URL)" || (echo "Set API_URL=https://api.example.com" && exit 2)
	uv run polygraphml-deployed-smoke --api-url "$(API_URL)" --output benchmark-results/deployed-smoke.json

deployment-preflight:
	./scripts/deployment-preflight.sh

check: lint typecheck test contracts
	git diff --check
