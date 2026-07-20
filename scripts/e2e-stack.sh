#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

cleanup() {
  jobs -p | xargs -r kill
  rm -f "${api_log:-}" "${worker_log:-}"
}

trap cleanup EXIT INT TERM

export POLYGRAPHML_ENVIRONMENT=test
export POLYGRAPHML_AGENT_MODE=fixture
export POLYGRAPHML_DATABASE_PATH=.polygraphml-data/e2e.db
export POLYGRAPHML_ARTIFACT_ROOT=.polygraphml-data/e2e-artifacts
export POLYGRAPHML_WORKER_POLL_SECONDS=0.05

# Prepare the environment before starting background processes.  Concurrent
# `uv run` calls can contend for the environment lock on a fresh CI runner.
uv sync --all-groups --frozen
runtime_python=".venv/bin/python"
api_log="$(mktemp)"
worker_log="$(mktemp)"

"${runtime_python}" -m uvicorn polygraphml.api.main:app --host 127.0.0.1 --port 8000 >"${api_log}" 2>&1 &
"${runtime_python}" -m polygraphml.worker.main >"${worker_log}" 2>&1 &
if ! "${runtime_python}" - <<'PY'
import time
import urllib.request

# Cold GitHub-hosted runners can take longer than ten seconds to import the
# analysis stack before Uvicorn binds its port.
for attempt in range(300):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/readyz", timeout=1) as response:
            if response.status == 200:
                break
    except OSError:
        if attempt == 299:
            raise
        time.sleep(0.1)
PY
then
  echo "API process log:" >&2
  cat "${api_log}" >&2
  echo "Worker process log:" >&2
  cat "${worker_log}" >&2
  exit 1
fi
npm --prefix frontend run dev -- --host 127.0.0.1
