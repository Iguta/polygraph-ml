from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from polygraphml.benchmarks.catalog import SYNTHETIC_BENCHMARK_ID


class DeployedSmokeRun(BaseModel):
    """Metadata-only evidence from one disposable public-path audit."""

    model_config = ConfigDict(extra="forbid")

    audit_id: str
    final_status: str
    duration_seconds: float = Field(ge=0)
    event_count: int = Field(ge=1)
    event_type_counts: dict[str, int]
    question_answered: bool
    confirmed_mechanisms: list[str]


class DeployedSmokeReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    created_at: datetime
    api_url: str
    mode: Literal["live", "fixture"]
    run_count: int = Field(ge=1)
    runs: list[DeployedSmokeRun]
    sensitive_data_included: Literal[False] = False
    event_payloads_included: Literal[False] = False


def _data(response: httpx.Response) -> dict[str, Any] | list[dict[str, Any]]:
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    if payload.get("error") is not None:
        raise RuntimeError(f"API returned an error: {payload['error'].get('code', 'UNKNOWN')}")
    data = payload.get("data")
    if not isinstance(data, (dict, list)):
        raise RuntimeError("API response has no data payload.")
    return data


def _answer_for(question: dict[str, Any]) -> str:
    options = question.get("options")
    if isinstance(options, list) and options:
        return "after" if "after" in options else str(options[0])
    return "The feature is not available until after the decision."


def run_deployed_smoke(
    api_url: str,
    *,
    mode: Literal["live", "fixture"] = "live",
    timeout_seconds: float = 180,
    poll_seconds: float = 1,
) -> DeployedSmokeRun:
    """Exercise a disposable audit through the deployed API and worker boundary."""

    base_url = api_url.rstrip("/")
    deadline = time.monotonic() + timeout_seconds
    project_id: str | None = None
    started = time.monotonic()
    with httpx.Client(base_url=base_url, timeout=20) as client:
        session = _data(client.post("/api/v1/sessions"))
        if not isinstance(session, dict):
            raise RuntimeError("Session response is malformed.")
        token = session.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Session response did not include an access token.")
        headers = {"Authorization": f"Bearer {token}"}
        try:
            project = _data(
                client.post(
                    "/api/v1/projects/from-benchmark",
                    headers=headers,
                    json={"benchmark_id": SYNTHETIC_BENCHMARK_ID},
                )
            )
            if not isinstance(project, dict) or not isinstance(project.get("project_id"), str):
                raise RuntimeError("Benchmark project response is malformed.")
            project_id = project["project_id"]
            scenarios = project.get("scenarios")
            if (
                not isinstance(scenarios, list)
                or not scenarios
                or not isinstance(scenarios[-1], dict)
            ):
                raise RuntimeError("Benchmark project did not include a scenario revision.")
            scenario = scenarios[-1]
            if not isinstance(scenario.get("revision"), int):
                raise RuntimeError("Benchmark scenario revision is malformed.")
            audit = _data(
                client.post(
                    "/api/v1/audits",
                    headers={**headers, "Idempotency-Key": uuid4().hex},
                    json={
                        "project_id": project_id,
                        "scenario_revision": scenario["revision"],
                        "mode": "complete_audit",
                    },
                )
            )
            if not isinstance(audit, dict) or not isinstance(audit.get("audit_id"), str):
                raise RuntimeError("Audit start response is malformed.")
            audit_id = audit["audit_id"]
            question_answered = False
            while time.monotonic() < deadline:
                current = _data(client.get(f"/api/v1/audits/{audit_id}", headers=headers))
                if not isinstance(current, dict):
                    raise RuntimeError("Audit read response is malformed.")
                status = current.get("status")
                if status == "waiting_for_user" and not question_answered:
                    questions = current.get("open_questions")
                    if not isinstance(questions, list) or not questions:
                        raise RuntimeError("Audit is waiting without an open question.")
                    question = questions[0]
                    if not isinstance(question, dict) or not isinstance(
                        question.get("question_id"), str
                    ):
                        raise RuntimeError("Open question is malformed.")
                    _data(
                        client.post(
                            f"/api/v1/audits/{audit_id}/answers",
                            headers={**headers, "Idempotency-Key": uuid4().hex},
                            json={
                                "question_id": question["question_id"],
                                "answer": _answer_for(question),
                            },
                        )
                    )
                    question_answered = True
                elif status == "complete":
                    events = _data(
                        client.get(
                            f"/api/v1/audits/{audit_id}/events",
                            headers={**headers, "Accept": "application/json"},
                        )
                    )
                    if not isinstance(events, list):
                        raise RuntimeError("Audit event replay response is malformed.")
                    findings = current.get("findings")
                    confirmed = (
                        sorted(
                            finding["mechanism"]
                            for finding in findings
                            if isinstance(finding, dict) and finding.get("status") == "confirmed"
                        )
                        if isinstance(findings, list)
                        else []
                    )
                    return DeployedSmokeRun(
                        audit_id=audit_id,
                        final_status=status,
                        duration_seconds=round(time.monotonic() - started, 3),
                        event_count=len(events),
                        event_type_counts=dict(
                            Counter(
                                str(event.get("type", "unknown"))
                                for event in events
                                if isinstance(event, dict)
                            )
                        ),
                        question_answered=question_answered,
                        confirmed_mechanisms=confirmed,
                    )
                elif status in {"failed", "failed_partial"}:
                    raise RuntimeError(f"Deployed audit ended with status {status}.")
                time.sleep(poll_seconds)
            raise TimeoutError(
                f"Deployed audit did not finish within {timeout_seconds:.0f} seconds."
            )
        finally:
            if project_id is not None:
                response = client.delete(f"/api/v1/projects/{project_id}", headers=headers)
                response.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a disposable audit through the deployed API and write metadata-only evidence."
    )
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--mode", choices=("live", "fixture"), default="live")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=180)
    parser.add_argument(
        "--output", type=Path, default=Path("benchmark-results/deployed-smoke.json")
    )
    arguments = parser.parse_args()
    if arguments.runs < 1:
        raise SystemExit("--runs must be at least 1")
    runs = [
        run_deployed_smoke(
            arguments.api_url,
            mode=arguments.mode,
            timeout_seconds=arguments.timeout_seconds,
        )
        for _ in range(arguments.runs)
    ]
    report = DeployedSmokeReport(
        created_at=datetime.now(UTC),
        api_url=arguments.api_url.rstrip("/"),
        mode=arguments.mode,
        run_count=len(runs),
        runs=runs,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Deployed smoke evidence written to {arguments.output}")


if __name__ == "__main__":
    main()
