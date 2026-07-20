#!/usr/bin/env bash
set -euo pipefail

cleanup() {
  jobs -p | xargs -r kill
}

trap cleanup EXIT INT TERM

uv run uvicorn polygraphml.api.main:app --reload --host 0.0.0.0 --port 8000 &
uv run python -m polygraphml.worker.main &
npm --prefix frontend run dev &

wait
