#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

cleanup() {
  jobs -p | xargs -r kill
}

trap cleanup EXIT INT TERM

export POLYGRAPHML_ENVIRONMENT=test
export POLYGRAPHML_AGENT_MODE=fixture
export POLYGRAPHML_DATABASE_PATH=.polygraphml-data/e2e.db
export POLYGRAPHML_ARTIFACT_ROOT=.polygraphml-data/e2e-artifacts
export POLYGRAPHML_WORKER_POLL_SECONDS=0.05

uv run uvicorn polygraphml.api.main:app --host 127.0.0.1 --port 8000 &
uv run python -m polygraphml.worker.main &
uv run python - <<'PY'
import time
import urllib.request

for attempt in range(100):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/readyz", timeout=1) as response:
            if response.status == 200:
                break
    except OSError:
        if attempt == 99:
            raise
        time.sleep(0.1)
PY
npm --prefix frontend run dev -- --host 127.0.0.1
