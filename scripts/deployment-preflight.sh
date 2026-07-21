#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}/.."

missing=0

report_check() {
  local label="$1"
  local status="$2"
  if [[ "${status}" == "true" ]]; then
    echo "PASS  ${label}"
  else
    echo "OPEN  ${label}"
    missing=$((missing + 1))
  fi
}

if uv run python - <<'PY' >/dev/null 2>&1
from polygraphml.config import Settings
raise SystemExit(0 if Settings(agent_mode="live").live_agent_ready else 1)
PY
then
  report_check "non-empty OPENAI_API_KEY" true
else
  report_check "non-empty OPENAI_API_KEY" false
fi

if command -v aws >/dev/null 2>&1 && aws sts get-caller-identity >/dev/null 2>&1; then
  report_check "authenticated AWS CLI" true
else
  report_check "authenticated AWS CLI" false
fi

if command -v vercel >/dev/null 2>&1 && vercel whoami >/dev/null 2>&1; then
  report_check "authenticated Vercel CLI" true
else
  report_check "authenticated Vercel CLI" false
fi

if find infra/terraform -maxdepth 1 -type f -name '*.tfvars' ! -name '*.example' -print -quit | grep -q .; then
  report_check "deployment .tfvars" true
else
  report_check "deployment .tfvars" false
fi

if uv run python - <<'PY' >/dev/null 2>&1
from pathlib import Path
from polygraphml.benchmarks.live_evaluate import LiveEvaluationResult
path = Path("benchmark-results/live-evaluation.json")
result = LiveEvaluationResult.model_validate_json(path.read_text())
assert result.mode == "live"
assert result.case_count == 3
assert result.passed is True
assert len(result.cases) == 3
assert all(case.agent_mode == "live" and case.passed for case in result.cases)
assert result.payloads_included is False
assert result.raw_chain_of_thought_stored is False
assert result.trace_include_sensitive_data is False
PY
then
  report_check "sanitized three-case live evaluation" true
else
  report_check "sanitized three-case live evaluation" false
fi

if uv run python - <<'PY' >/dev/null 2>&1
from pathlib import Path
from polygraphml.operations.deployed_smoke import DeployedSmokeReport
report = DeployedSmokeReport.model_validate_json(Path("benchmark-results/deployed-smoke.json").read_text())
assert report.mode == "live"
assert report.sensitive_data_included is False
assert report.event_payloads_included is False
assert all(run.final_status == "complete" and run.question_answered for run in report.runs)
PY
then
  report_check "deployed live audit, replay, and deletion smoke" true
else
  report_check "deployed live audit, replay, and deletion smoke" false
fi

if git status --porcelain | grep -q .; then
  report_check "reviewed clean Git working tree" false
else
  report_check "reviewed clean Git working tree" true
fi

if uv run python - <<'PY' >/dev/null 2>&1
import json
from pathlib import Path
payload = json.loads(Path("benchmark-results/latest.json").read_text())
aggregate = payload["aggregate"]
assert aggregate["false_confirmations"] == 0
assert aggregate["false_negatives"] == 0
assert aggregate["precision"] == 1.0
assert aggregate["recall"] == 1.0
PY
then
  report_check "fixture benchmark release gate" true
else
  report_check "fixture benchmark release gate" false
fi

if [[ "${missing}" -gt 0 ]]; then
  echo "Deployment preflight has ${missing} open gate(s)."
  exit 1
fi

echo "Deployment preflight passed."
