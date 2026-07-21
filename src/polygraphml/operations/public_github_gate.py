from __future__ import annotations

import argparse
import asyncio
import json
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from polygraphml.api.container import build_container
from polygraphml.config import Settings
from polygraphml.domain.models import (
    Artifact,
    Audit,
    AuditMode,
    AuditStatus,
    Finding,
    FindingStatus,
    ProjectStatus,
    Question,
)
from polygraphml.worker.coordinator import AuditCoordinator

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class PublicGitHubGateReport(BaseModel):
    """Sanitized evidence for the immutable public-repository release gate."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    created_at: datetime
    repository_url: str
    requested_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    resolved_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    manifest_imported: Literal[True] = True
    artifact_count: int = Field(ge=4)
    artifact_hashes: dict[str, Sha256]
    audit_status: Literal["complete"]
    event_count: int = Field(ge=1)
    question_answered: Literal[True] = True
    confirmed_pairs: list[str]
    metric: Literal["roc_auc"]
    reported_metric: float
    reproduced_metric: float
    corrected_metric: float
    agent_mode: Literal["fixture"] = "fixture"
    payloads_included: Literal[False] = False
    sensitive_data_included: Literal[False] = False


def _after_decision_answer(question: Question) -> str:
    for option in question.options:
        normalized = option.lower().replace(" ", "_")
        if "after" in normalized or "not_available" in normalized:
            return option
    raise RuntimeError("Flagship question did not offer the declared post-decision answer.")


async def run_public_github_gate(
    repository_url: str,
    commit: str,
    *,
    expected_pair: str = "post_outcome:duration",
) -> PublicGitHubGateReport:
    if FULL_SHA.fullmatch(commit) is None:
        raise ValueError(
            "The public GitHub gate requires a full lowercase 40-character commit SHA."
        )

    with tempfile.TemporaryDirectory(prefix="polygraphml-public-github-") as temporary:
        root = Path(temporary)
        settings = Settings(
            environment="test",
            agent_mode="fixture",
            database_path=root / "state.db",
            artifact_root=root / "artifacts",
            worker_lease_seconds=300,
        )
        container = build_container(settings)
        coordinator = AuditCoordinator(
            settings, container.repository, container.artifacts, container.queue
        )
        try:
            session, _ = container.repository.create_session(3600)
            project = await container.projects.create_github_project(
                session,
                "Public UCI Bank flagship",
                repository_url,
                commit,
            )
            if project.status != ProjectStatus.READY:
                raise RuntimeError(f"Imported project is not audit-ready: {project.status.value}.")
            if project.source.resolved_commit != commit:
                raise RuntimeError("GitHub resolved a commit different from the requested SHA.")

            artifacts = [
                artifact
                for artifact_id in project.artifact_ids
                if (artifact := container.repository.get(Artifact, artifact_id)) is not None
            ]
            if any(
                not artifact.source_ref
                or not artifact.source_ref.startswith("github:")
                or not artifact.source_ref.endswith(f"@{commit}")
                for artifact in artifacts
            ):
                raise RuntimeError(
                    "An imported artifact is missing its immutable source reference."
                )
            artifact_hashes = {
                str(artifact.source_ref)
                .split("@", maxsplit=1)[0]
                .removeprefix("github:"): artifact.sha256
                for artifact in artifacts
            }
            manifest_imported = any(
                artifact.filename == ".polygraphml.yml" for artifact in artifacts
            )
            if not manifest_imported:
                raise RuntimeError(
                    "The immutable import did not use the root PolygraphML manifest."
                )

            scenario = project.current_scenario
            if scenario is None:
                raise RuntimeError("The root manifest did not produce a scenario revision.")
            audit = container.audits.start(
                session,
                project,
                scenario.revision,
                AuditMode.COMPLETE,
                "public-github-gate-start",
            )
            start_job = container.queue.receive()
            if start_job is None:
                raise RuntimeError("Public GitHub gate start job was not queued.")
            await coordinator.process(start_job)

            waiting = container.repository.get(Audit, audit.audit_id)
            if (
                waiting is None
                or waiting.status != AuditStatus.WAITING_FOR_USER
                or not waiting.question_ids
            ):
                raise RuntimeError("Public GitHub audit did not persist its material question.")
            question = container.repository.get(Question, waiting.question_ids[-1])
            if question is None:
                raise RuntimeError("Public GitHub audit question was not persisted.")
            container.audits.answer(
                session,
                waiting,
                question,
                _after_decision_answer(question),
                "public-github-gate-answer",
            )
            resume_job = container.queue.receive()
            if resume_job is None:
                raise RuntimeError("Public GitHub gate resume job was not queued.")
            await coordinator.process(resume_job)

            completed = container.repository.get(Audit, audit.audit_id)
            if completed is None or completed.status != AuditStatus.COMPLETE:
                status = completed.status.value if completed is not None else "missing"
                raise RuntimeError(f"Public GitHub audit did not complete: {status}.")
            comparison = completed.metric_comparison
            if (
                comparison is None
                or comparison.reported is None
                or comparison.reproduced is None
                or comparison.corrected is None
            ):
                raise RuntimeError("Public GitHub audit did not produce all three metric values.")
            if comparison.metric != "roc_auc":
                raise RuntimeError("The flagship public audit did not reproduce ROC AUC.")
            findings = [
                finding
                for finding_id in completed.finding_ids
                if (finding := container.repository.get(Finding, finding_id)) is not None
            ]
            confirmed_pairs = sorted(
                f"{finding.mechanism.value}:{finding.features[0]}"
                for finding in findings
                if finding.status == FindingStatus.CONFIRMED and finding.features
            )
            if confirmed_pairs != [expected_pair]:
                raise RuntimeError(
                    "Public GitHub audit did not produce the predeclared flagship finding."
                )
            return PublicGitHubGateReport(
                created_at=datetime.now(UTC),
                repository_url=repository_url,
                requested_commit=commit,
                resolved_commit=project.source.resolved_commit,
                artifact_count=len(artifacts),
                artifact_hashes=artifact_hashes,
                audit_status="complete",
                event_count=len(container.repository.list_events(audit.audit_id)),
                confirmed_pairs=confirmed_pairs,
                metric=comparison.metric,
                reported_metric=comparison.reported.value,
                reproduced_metric=comparison.reproduced.value,
                corrected_metric=comparison.corrected.value,
            )
        finally:
            container.repository.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import and audit the flagship through a pinned public GitHub commit."
    )
    parser.add_argument("--repository-url", default="https://github.com/Iguta/polygraph-ml")
    parser.add_argument("--commit", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/public-github-gate.json"),
    )
    arguments = parser.parse_args()
    try:
        report = asyncio.run(run_public_github_gate(arguments.repository_url, arguments.commit))
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    rendered = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")
    print(f"Sanitized public GitHub gate evidence written to {arguments.output}")


if __name__ == "__main__":
    main()
